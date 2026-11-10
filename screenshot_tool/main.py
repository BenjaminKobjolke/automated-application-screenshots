#!/usr/bin/env python3
"""
Automated Screenshot Tool for Multi-Language Windows Applications

Captures screenshots of a target application in all its supported languages
by automatically cycling through its language dropdown. The target app is
defined by a JSON config file (default: config/keyboard-layout-watcher.json).

Also records animated demos (GIF/MP4 + stills) of apps implementing the
automation-demo contract (docs/AUTOMATION_INTERFACE.md).

Usage:
    uv run screenshot-tool              # Capture all languages
    uv run screenshot-tool --list       # List supported languages
    uv run screenshot-tool --start-from de  # Start from German
    uv run screenshot-tool --delay 0.5  # Custom delay between captures
    uv run screenshot-tool --config config/other-app.json  # Other target app
    uv run screenshot-tool --config config/ax-suite.local.json  # Capture configured web pages
    uv run screenshot-tool --config config/app.json --demo 1    # Record demo 1
    uv run screenshot-tool --config config/app.json --demo all  # Record all demos
    uv run screenshot-tool --config config/app.json --compose   # Build the artifacts
    uv run screenshot-tool --config config/app.json --demo all --compose  # Both
"""

import argparse
import io
import sys
from dataclasses import replace
from pathlib import Path

from . import config, idle_guard
from .app_logger import AppLogger
from .cli import ScreenshotCLI
from .config_listing import list_config
from .live_cli import LiveCLI
from .live_config import LiveSettings, LiveTarget
from .live_session import LiveSession
from .web_config import WebDevice


def setup_utf8_console() -> None:
    """Configure console for UTF-8 output on Windows."""
    if sys.platform == "win32":
        # Set console output to UTF-8
        sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")
        sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding="utf-8", errors="replace")


def main() -> int:
    """Main entry point.

    Returns:
        Exit code (0 for success, non-zero for errors)
    """
    setup_utf8_console()
    parser = argparse.ArgumentParser(
    description="Capture screenshots of configured desktop and web applications",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  uv run screenshot-tool                    # Capture all languages
  uv run screenshot-tool --list             # Show all language codes
  uv run screenshot-tool --start-from de    # Start from German
  uv run screenshot-tool --output ./imgs    # Custom output directory
  uv run screenshot-tool --delay 0.5        # Wait 0.5s between captures
  uv run screenshot-tool --config config/other-app.json  # Other target app
  uv run screenshot-tool -c config/app.json --demo all --compose  # Record + build
  uv run screenshot-tool -c config/app.json --output ./check --demo 1 --stills-only  # Stills only, into ./check
  uv run screenshot-tool --config config/web.json --device mobile  # Capture web pages as a phone
  uv run screenshot-tool --config config/web.json --device mobile --full-page  # Whole page as a phone
        """,
    )

    parser.add_argument(
        "--config",
        "-c",
        metavar="PATH",
        help=f"App config JSON file (default: {config.DEFAULT_CONFIG_PATH})",
    )

    parser.add_argument("--output", "-o", help="Output directory (default: from config)")
    parser.add_argument(
        "--device",
        choices=[device.value for device in WebDevice],
        default=WebDevice.DESKTOP.value,
        help="Capture web pages as desktop or as an emulated phone (plain web run only)",
    )
    parser.add_argument(
        "--full-page",
        action="store_true",
        help="Capture the whole scrollable page instead of the viewport (plain web run only)",
    )

    parser.add_argument(
        "--start-from",
        "-s",
        metavar="CODE",
        help="Language code to start from (skips earlier languages)",
    )

    parser.add_argument(
        "--delay",
        "-d",
        type=float,
        help="Delay in seconds after each language change (default: from config)",
    )

    parser.add_argument(
        "--list",
        "-l",
        action="store_true",
        help="List what this config can record and build, and exit",
    )

    parser.add_argument(
        "--demo",
        metavar="ID|all",
        help="Record the given demo (or all demos) of the configured app and exit",
    )
    parser.add_argument(
        "--stills-only",
        action="store_true",
        help="With --demo: record only the stills; skip frame capture and GIF/MP4 export",
    )

    parser.add_argument(
        "--compose",
        metavar="ALL|NAME",
        nargs="?",
        const="all",
        help="Build the config's compose steps (all, or the ones whose output "
        "or type matches NAME). Combine with --demo to record and build in one run.",
    )

    parser.add_argument(
        "--live",
        action="store_true",
        help="Keep a Flutter app running and accept JSON-lines live commands",
    )
    parser.add_argument(
        "--target",
        choices=[target.value for target in LiveTarget],
        help="Override the live config target",
    )
    parser.add_argument(
        "--skip-idle-check",
        action="store_true",
        help="Start without checking whether someone is using the PC",
    )

    args = parser.parse_args()

    if args.live and (args.demo or args.compose or args.list or args.start_from):
        parser.error("--live cannot be combined with --demo, --compose, --list or --start-from")
    if args.target and not args.live:
        parser.error("--target requires --live")
    if (args.demo or args.compose) and (args.list or args.start_from):
        parser.error("--demo/--compose cannot be combined with --list or --start-from")
    if args.stills_only and (not args.demo or args.compose):
        parser.error("--stills-only requires --demo and cannot be combined with --compose")
    if args.device == WebDevice.MOBILE.value and (
        args.live or args.demo or args.compose or args.list
    ):
        parser.error("--device mobile cannot be combined with --live, --demo, --compose or --list")
    if args.full_page and (args.live or args.demo or args.compose or args.list):
        parser.error("--full-page cannot be combined with --live, --demo, --compose or --list")

    if args.config:
        config.load_config(args.config)
    _apply_demo_overrides(args)

    if args.device == WebDevice.MOBILE.value and config.settings.web is None:
        parser.error("--device mobile requires a config with a web section")
    if args.full_page and config.settings.web is None:
        parser.error("--full-page requires a config with a web section")

    live_settings = config.settings.live
    if args.live and live_settings is None:
        parser.error("--live requires a config with a live section")
    if args.live and args.target:
        live_settings = replace(live_settings, target=LiveTarget(args.target))

    if args.live:
        AppLogger.configure(stream=sys.stderr)

    shows = idle_guard.shows_windows(
        list_mode=args.list,
        demo=bool(args.demo),
        compose=bool(args.compose),
        live=args.live,
        live_settings=live_settings,
        web_settings=config.settings.web,
    )
    if shows:
        idle_guard.close_leftover_alerts()
    warned = not args.skip_idle_check and shows and idle_guard.warn_if_active()
    try:
        return _run(args, live_settings)
    finally:
        if warned:
            idle_guard.notify_done()


def _run(args: argparse.Namespace, live_settings: LiveSettings | None) -> int:
    """Dispatch a parsed screenshot command to its selected workflow."""
    if args.live:
        assert live_settings is not None
        AppLogger.info("Starting live screenshot session")
        return LiveCLI(LiveSession(live_settings), sys.stdin, sys.stdout).run()

    if args.list:
        list_config()
        return 0

    if args.demo:
        from .demo_cli import DemoCLI

        code = DemoCLI().run(args.demo)
        # A failed recording makes the compose step build stale inputs.
        if code or not args.compose:
            return code

    if args.compose:
        from . import compose

        return compose.run(args.compose)

    if config.settings.web is not None:
        from .web_pages_cli import WebPagesCLI

        return WebPagesCLI(
            config.settings.web,
            output_dir=Path(args.output) if args.output else None,
            device=WebDevice(args.device),
            full_page=args.full_page,
        ).run(start_from=args.start_from)

    # Create CLI instance
    cli = ScreenshotCLI(output_dir=args.output, delay=args.delay)

    # Run automated capture
    return cli.run_automated(start_from=args.start_from)


def _apply_demo_overrides(args: argparse.Namespace) -> None:
    """Apply output and format overrides shared by demo and compose runs."""
    if args.output and (args.demo or args.compose):
        config.settings = replace(config.settings, output_dir=str(Path(args.output).resolve()))
    if args.stills_only:
        config.settings = replace(
            config.settings,
            demos=tuple(replace(demo, formats=("png",)) for demo in config.settings.demos),
        )


if __name__ == "__main__":
    sys.exit(main())
