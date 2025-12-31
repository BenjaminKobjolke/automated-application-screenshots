#!/usr/bin/env python3
"""
Automated Screenshot Tool for Multi-Language Windows Applications

Captures screenshots of KeyboardLayoutWatcher in all 41 supported languages
by automatically cycling through the language dropdown.

Usage:
    uv run screenshot-tool              # Capture all languages
    uv run screenshot-tool --list       # List supported languages
    uv run screenshot-tool --start-from de  # Start from German
    uv run screenshot-tool --delay 0.5  # Custom delay between captures
"""

import argparse
import io
import sys

from .cli import ScreenshotCLI
from .config import DEFAULT_OUTPUT_DIR, DELAY_AFTER_CHANGE


def setup_utf8_console() -> None:
    """Configure console for UTF-8 output on Windows."""
    if sys.platform == 'win32':
        # Set console output to UTF-8
        sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')
        sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding='utf-8', errors='replace')


def main() -> int:
    """Main entry point.

    Returns:
        Exit code (0 for success, non-zero for errors)
    """
    setup_utf8_console()
    parser = argparse.ArgumentParser(
        description='Capture screenshots of KeyboardLayoutWatcher in multiple languages',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  uv run screenshot-tool                    # Capture all 41 languages
  uv run screenshot-tool --list             # Show all language codes
  uv run screenshot-tool --start-from de    # Start from German
  uv run screenshot-tool --output ./imgs    # Custom output directory
  uv run screenshot-tool --delay 0.5        # Wait 0.5s between captures
        """
    )

    parser.add_argument(
        '--output', '-o',
        default=DEFAULT_OUTPUT_DIR,
        help=f'Output directory (default: {DEFAULT_OUTPUT_DIR})'
    )

    parser.add_argument(
        '--start-from', '-s',
        metavar='CODE',
        help='Language code to start from (skips earlier languages)'
    )

    parser.add_argument(
        '--delay', '-d',
        type=float,
        default=DELAY_AFTER_CHANGE,
        help=f'Delay in seconds after each language change (default: {DELAY_AFTER_CHANGE})'
    )

    parser.add_argument(
        '--list', '-l',
        action='store_true',
        help='List all supported language codes and exit'
    )

    args = parser.parse_args()

    # Create CLI instance
    cli = ScreenshotCLI(output_dir=args.output, delay=args.delay)

    # Handle --list
    if args.list:
        cli.list_languages()
        return 0

    # Run automated capture
    return cli.run_automated(start_from=args.start_from)


if __name__ == '__main__':
    sys.exit(main())
