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
    uv run screenshot-tool --config config/app.json --demo 1    # Record demo 1
    uv run screenshot-tool --config config/app.json --demo all  # Record all demos
    uv run screenshot-tool --config config/app.json --compose   # Build the artifacts
    uv run screenshot-tool --config config/app.json --demo all --compose  # Both
"""

import argparse
import io
import sys

from . import config
from .app_logger import AppLogger
from .cli import ScreenshotCLI


def setup_utf8_console() -> None:
    """Configure console for UTF-8 output on Windows."""
    if sys.platform == "win32":
        # Set console output to UTF-8
        sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")
        sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding="utf-8", errors="replace")


def list_config() -> None:
    """Print what the loaded config can record and build.

    The config is the only place that knows which demos exist, what they are
    grouped into and what gets built from them - reading it back is cheaper
    than reading the JSON, and it can't drift from what the tool will do.
    """
    settings = config.settings
    if settings.demos:
        AppLogger.info("Demos:")
        for demo in settings.demos:
            details = [f"{demo.width}x{demo.height}" if demo.width else "", f"{demo.fps} fps"]
            details.append("/".join(demo.formats) if demo.formats else "stills only")
            if demo.group:
                details.append(f"group: {demo.group}")
            if demo.languages:
                details.append(f"languages: {', '.join(demo.languages)}")
            AppLogger.info(
                f"  {demo.id:>3}  {demo.name:<24} {'  '.join(d for d in details if d)}"
            )
    if settings.compose:
        AppLogger.info("\nCompose steps:")
        for step in settings.compose:
            source = f"group {step.group}" if step.group else f"demo {step.demo}"
            budget = f", max {step.max_size / 1000 / 1000:.1f}MB" if step.max_size else ""
            AppLogger.info(f"  {step.type:<12} {step.output:<32} from {source}{budget}")
    if settings.language_names:
        AppLogger.info("\nLanguages:")
        ScreenshotCLI().list_languages()
    if not (settings.demos or settings.compose or settings.language_names):
        AppLogger.info("This config defines no demos, compose steps or languages.")


def main() -> int:
    """Main entry point.

    Returns:
        Exit code (0 for success, non-zero for errors)
    """
    setup_utf8_console()
    parser = argparse.ArgumentParser(
        description="Capture screenshots of a Windows application in multiple languages",
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
        "--compose",
        metavar="ALL|NAME",
        nargs="?",
        const="all",
        help="Build the config's compose steps (all, or the ones whose output "
        "or type matches NAME). Combine with --demo to record and build in one run.",
    )

    args = parser.parse_args()

    if (args.demo or args.compose) and (args.list or args.start_from):
        parser.error("--demo/--compose cannot be combined with --list or --start-from")

    if args.config:
        config.load_config(args.config)

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

    # Create CLI instance
    cli = ScreenshotCLI(output_dir=args.output, delay=args.delay)

    # Run automated capture
    return cli.run_automated(start_from=args.start_from)


if __name__ == "__main__":
    sys.exit(main())
