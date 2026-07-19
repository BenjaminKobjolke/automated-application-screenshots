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
"""

import argparse
import io
import sys

from . import config
from .cli import ScreenshotCLI


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
        "--list", "-l", action="store_true", help="List all supported language codes and exit"
    )

    parser.add_argument(
        "--demo",
        metavar="ID|all",
        help="Record the given demo (or all demos) of the configured app and exit",
    )

    args = parser.parse_args()

    if args.demo and (args.list or args.start_from):
        parser.error("--demo cannot be combined with --list or --start-from")

    if args.config:
        config.load_config(args.config)

    if args.demo:
        from .demo_cli import DemoCLI

        return DemoCLI().run(args.demo)

    # Create CLI instance
    cli = ScreenshotCLI(output_dir=args.output, delay=args.delay)

    # Handle --list
    if args.list:
        cli.list_languages()
        return 0

    # Run automated capture
    return cli.run_automated(start_from=args.start_from)


if __name__ == "__main__":
    sys.exit(main())
