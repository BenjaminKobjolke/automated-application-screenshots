"""Command-line interface for automated screenshot capture."""

import sys
import time
from pathlib import Path

import keyboard

from . import config
from .automation import DropdownAutomation
from .capture import WindowCapture
from .dropdown_reader import DropdownReader
from .window_finder import WindowFinder


class ScreenshotCLI:
    """Automated CLI for capturing multi-language screenshots."""

    def __init__(self, output_dir: str | None = None, delay: float | None = None):
        """Initialize the CLI.

        Args:
            output_dir: Directory to save screenshots (defaults to config value)
            delay: Delay in seconds after each language change (defaults to config value)
        """
        self.output_dir = Path(output_dir or config.DEFAULT_OUTPUT_DIR)
        self.delay = config.DELAY_AFTER_CHANGE if delay is None else delay
        self.hwnd = None
        self.automation = None
        self.dropdown_reader = None
        self.captured = []
        self.failed = []

    def find_window(self) -> bool:
        """Locate the target application window.

        Returns:
            True if window was found
        """
        print(f"Looking for {config.APP_PROCESS_NAME}...")

        # Try by process name first
        self.hwnd = WindowFinder.find_by_process_name(config.APP_PROCESS_NAME)
        if self.hwnd:
            title = WindowFinder.get_window_title(self.hwnd)
            print(f"Found window by process name: '{title}' (handle: {self.hwnd})")
            return True

        # Fallback to title search
        print(f"Process not found, searching by title '{config.APP_TITLE_SUBSTRING}'...")
        self.hwnd = WindowFinder.find_by_title_substring(config.APP_TITLE_SUBSTRING)
        if self.hwnd:
            title = WindowFinder.get_window_title(self.hwnd)
            print(f"Found window by title: '{title}' (handle: {self.hwnd})")
            return True

        print(f"ERROR: Could not find window for '{config.APP_TITLE_SUBSTRING}'.")
        print("Make sure the application is running and visible.")
        return False

    def capture_language(self, index: int, total: int) -> bool:
        """Capture screenshot for the current language shown in dropdown.

        Args:
            index: Current index (1-based)
            total: Total number of languages

        Returns:
            True if capture was successful
        """
        try:
            # Wait for UI to update
            time.sleep(self.delay)

            # Verify window is still valid
            if not WindowFinder.is_window_valid(self.hwnd):
                print(f"  ERROR: Window closed unexpectedly")
                return False

            # Read actual language from dropdown
            display_name = self.dropdown_reader.get_selected_language()
            if not display_name:
                print(f"[{index}/{total}] ERROR: Could not read dropdown value")
                self.failed.append(("unknown", "Could not read dropdown"))
                return False

            # Get language code from display name
            lang_code = config.NAME_TO_CODE.get(display_name)
            if not lang_code:
                print(f"[{index}/{total}] ERROR: Unknown language '{display_name}'")
                self.failed.append((display_name, "Unknown language name"))
                return False

            # Capture screenshot
            image = WindowCapture.capture_window(self.hwnd)

            # Save in language subfolder (e.g., screenshots/de/main.png)
            output_path = self.output_dir / lang_code / config.SCREENSHOT_FILENAME
            WindowCapture.save_screenshot(image, output_path)

            print(f"[{index}/{total}] {lang_code} - {display_name}... saved")
            self.captured.append(lang_code)
            return True

        except Exception as e:
            print(f"[{index}/{total}] FAILED: {e}")
            self.failed.append(("unknown", str(e)))
            return False

    def run_automated(self, start_from: str | None = None) -> int:
        """Run fully automated capture session.

        Args:
            start_from: Optional language code to start from

        Returns:
            Exit code (0 for success, 1 for errors)
        """
        # Find window
        if not self.find_window():
            return 1

        # Wait for F1 to start
        print("\nPress F1 to start capturing...")
        keyboard.wait('f1')
        print("Starting...\n")

        # Determine languages to capture
        languages = config.LANGUAGE_CODES.copy()
        if start_from:
            if start_from not in languages:
                print(f"ERROR: Unknown language code '{start_from}'")
                print(f"Available codes: {', '.join(languages)}")
                return 1
            start_index = languages.index(start_from)
            languages = languages[start_index:]
            print(f"Starting from '{start_from}' ({len(languages)} languages)")

        total = len(languages)
        print(f"\nBringing window to foreground...")
        WindowFinder.bring_to_foreground(self.hwnd)
        time.sleep(0.3)

        # Initialize automation and dropdown reader
        self.automation = DropdownAutomation(self.hwnd)
        self.dropdown_reader = DropdownReader(self.hwnd)
        if not self.dropdown_reader.connect():
            print("ERROR: Could not connect to window for reading dropdown")
            return 1

        print("Focusing language dropdown...")
        self.automation.focus_dropdown()
        time.sleep(0.2)

        # Go to first language in our list
        if not start_from:
            first_name = config.LANGUAGE_NAMES.get(languages[0], languages[0])
            print(f"Going to first language ({first_name})...")
            self.automation.go_to_first()
            time.sleep(0.2)

        print(f"\nCapturing {total} languages automatically...\n")

        # Capture each language
        for i in range(1, total + 1):
            # Capture current language (reads dropdown to determine which one)
            self.capture_language(i, total)

            # Move to next language (except for the last one)
            if i < total:
                self.automation.next_item()

        # Print summary
        print(f"\n{'=' * 50}")
        print(f"Capture complete!")
        print(f"  Captured: {len(self.captured)}/{total}")
        if self.failed:
            print(f"  Failed: {len(self.failed)}")
            for code, error in self.failed:
                print(f"    - {code}: {error}")
        print(f"  Output: {self.output_dir.absolute()}")

        return 0 if not self.failed else 1

    def list_languages(self) -> None:
        """Print all supported language codes."""
        print("Supported language codes:\n")
        for i, code in enumerate(config.LANGUAGE_CODES, 1):
            name = config.LANGUAGE_NAMES.get(code, "")
            print(f"  {code:4} - {name}")
        print(f"\nTotal: {len(config.LANGUAGE_CODES)} languages")
