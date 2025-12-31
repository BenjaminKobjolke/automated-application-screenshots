"""Dropdown control automation using pyautogui."""

import time

import pyautogui

from .config import DROPDOWN_RELATIVE_POS
from .window_finder import WindowFinder


class DropdownAutomation:
    """Automate dropdown control interactions."""

    def __init__(self, hwnd: int):
        """Initialize with window handle.

        Args:
            hwnd: Window handle of the target application
        """
        self.hwnd = hwnd
        # Disable pyautogui failsafe (move mouse to corner to abort)
        pyautogui.FAILSAFE = True
        # Set a small pause between actions
        pyautogui.PAUSE = 0.1

    def get_dropdown_position(self) -> tuple[int, int]:
        """Calculate absolute screen position of the dropdown.

        Returns:
            Tuple of (x, y) screen coordinates for dropdown center
        """
        rect = WindowFinder.get_window_rect(self.hwnd)
        window_left, window_top = rect[0], rect[1]

        dropdown_x = window_left + DROPDOWN_RELATIVE_POS[0]
        dropdown_y = window_top + DROPDOWN_RELATIVE_POS[1]

        return (dropdown_x, dropdown_y)

    def focus_dropdown(self) -> None:
        """Click on the dropdown to focus it."""
        x, y = self.get_dropdown_position()
        pyautogui.click(x, y)
        time.sleep(0.1)

    def go_to_first(self) -> None:
        """Press Home key to go to first item in dropdown."""
        pyautogui.press('home')
        time.sleep(0.1)

    def next_item(self) -> None:
        """Press Down arrow to move to next item."""
        pyautogui.press('down')

    def select_current(self) -> None:
        """Press Enter to select current item (if dropdown is open)."""
        pyautogui.press('enter')

    def close_dropdown(self) -> None:
        """Press Escape to close dropdown without selecting."""
        pyautogui.press('escape')
