"""Command-line interface for automated screenshot capture."""

import time
from pathlib import Path

import keyboard

from . import config
from .app_logger import AppLogger
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
        self.output_dir = Path(output_dir or config.settings.output_dir)
        self.delay = config.settings.delay_after_change if delay is None else delay
        self.hwnd: int | None = None
        self.automation: DropdownAutomation | None = None
        self.dropdown_reader: DropdownReader | None = None
        self.captured: list[str] = []
        self.failed: list[tuple[str, str]] = []

    def find_window(self) -> bool:
        """Locate the target application window.

        Returns:
            True if window was found
        """
        AppLogger.info(f"Looking for {config.settings.process_name}...")

        self.hwnd = WindowFinder.find_by_process_name(config.settings.process_name)
        if self.hwnd:
            title = WindowFinder.get_window_title(self.hwnd)
            AppLogger.info(f"Found window by process name: '{title}' (handle: {self.hwnd})")
            return True

        AppLogger.info(
            f"Process not found, searching by title '{config.settings.title_substring}'..."
        )
        self.hwnd = WindowFinder.find_by_title_substring(config.settings.title_substring)
        if self.hwnd:
            title = WindowFinder.get_window_title(self.hwnd)
            AppLogger.info(f"Found window by title: '{title}' (handle: {self.hwnd})")
            return True

        AppLogger.error(f"Could not find window for '{config.settings.title_substring}'.")
        AppLogger.error("Make sure the application is running and visible.")
        return False

    def capture_language(self, index: int, total: int) -> bool:
        """Capture screenshot for the current language shown in dropdown.

        Args:
            index: Current index (1-based)
            total: Total number of languages

        Returns:
            True if capture was successful
        """
        assert self.hwnd is not None and self.dropdown_reader is not None
        try:
            time.sleep(self.delay)

            if not WindowFinder.is_window_valid(self.hwnd):
                AppLogger.error("Window closed unexpectedly")
                return False

            display_name = self.dropdown_reader.get_selected_language()
            if not display_name:
                AppLogger.error(f"[{index}/{total}] Could not read dropdown value")
                self.failed.append(("unknown", "Could not read dropdown"))
                return False

            lang_code = DropdownReader.lookup_code(display_name)
            if not lang_code:
                AppLogger.error(f"[{index}/{total}] Unknown language '{display_name}'")
                self.failed.append((display_name, "Unknown language name"))
                return False

            image = WindowCapture.capture_window(self.hwnd)

            # Save in language subfolder (e.g., screenshots/de/main.png)
            output_path = self.output_dir / lang_code / config.settings.screenshot_filename
            WindowCapture.save_screenshot(image, output_path)

            AppLogger.info(f"[{index}/{total}] {lang_code} - {display_name}... saved")
            self.captured.append(lang_code)
            return True

        except Exception as e:
            AppLogger.error(f"[{index}/{total}] FAILED: {e}")
            self.failed.append(("unknown", str(e)))
            return False

    def run_automated(self, start_from: str | None = None) -> int:
        """Run fully automated capture session.

        Args:
            start_from: Optional language code to start from

        Returns:
            Exit code (0 for success, 1 for errors)
        """
        if not self.find_window():
            return 1
        assert self.hwnd is not None

        AppLogger.info("\nPress F1 to start capturing...")
        keyboard.wait("f1")
        AppLogger.info("Starting...\n")

        languages = config.settings.language_codes.copy()
        if start_from:
            if start_from not in languages:
                AppLogger.error(f"Unknown language code '{start_from}'")
                AppLogger.error(f"Available codes: {', '.join(languages)}")
                return 1
            start_index = languages.index(start_from)
            languages = languages[start_index:]
            AppLogger.info(f"Starting from '{start_from}' ({len(languages)} languages)")

        total = len(languages)
        AppLogger.info("\nBringing window to foreground...")
        WindowFinder.bring_to_foreground(self.hwnd)
        time.sleep(0.3)

        self.automation = DropdownAutomation(self.hwnd)
        self.dropdown_reader = DropdownReader(self.hwnd)
        if not self.dropdown_reader.connect():
            AppLogger.error("Could not connect to window for reading dropdown")
            return 1

        AppLogger.info("Focusing language dropdown...")
        self.automation.focus_dropdown()
        time.sleep(0.2)

        if not start_from:
            first_name = config.settings.language_names.get(languages[0], languages[0])
            AppLogger.info(f"Going to first language ({first_name})...")
            self.automation.go_to_first()
            time.sleep(0.2)

        AppLogger.info(f"\nCapturing {total} languages automatically...\n")

        for i in range(1, total + 1):
            self.capture_language(i, total)
            if i < total:
                self.automation.next_item()

        AppLogger.info(f"\n{'=' * 50}")
        AppLogger.info("Capture complete!")
        AppLogger.info(f"  Captured: {len(self.captured)}/{total}")
        if self.failed:
            AppLogger.info(f"  Failed: {len(self.failed)}")
            for code, error in self.failed:
                AppLogger.info(f"    - {code}: {error}")
        AppLogger.info(f"  Output: {self.output_dir.absolute()}")

        return 0 if not self.failed else 1

    def list_languages(self) -> None:
        """Log all supported language codes."""
        AppLogger.info("Supported language codes:\n")
        for code in config.settings.language_codes:
            name = config.settings.language_names.get(code, "")
            AppLogger.info(f"  {code:4} - {name}")
        AppLogger.info(f"\nTotal: {len(config.settings.language_codes)} languages")
