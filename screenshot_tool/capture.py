"""Screenshot capture logic using pyautogui for reliable cross-DPI capture."""

import ctypes
from ctypes import wintypes
from pathlib import Path

import pyautogui
from PIL import Image

# Load Windows DLLs
user32 = ctypes.windll.user32

# Enable DPI awareness for accurate window positioning
try:
    ctypes.windll.shcore.SetProcessDpiAwareness(2)  # PROCESS_PER_MONITOR_DPI_AWARE
except Exception:
    try:
        user32.SetProcessDPIAware()
    except Exception:
        pass


class WindowCapture:
    """Capture screenshots of Windows application windows."""

    @staticmethod
    def capture_window(hwnd: int) -> Image.Image:
        """Capture a window and return as PIL Image.

        Uses pyautogui for reliable capture with proper DPI handling.

        Args:
            hwnd: Window handle to capture

        Returns:
            PIL Image of the window

        Raises:
            RuntimeError: If capture fails
        """
        # Get window rectangle using DPI-aware API
        rect = wintypes.RECT()
        user32.GetWindowRect(hwnd, ctypes.byref(rect))

        left = rect.left
        top = rect.top
        width = rect.right - rect.left
        height = rect.bottom - rect.top

        if width <= 0 or height <= 0:
            raise RuntimeError(f"Invalid window dimensions: {width}x{height}")

        # Use pyautogui to capture the screen region
        # This handles DPI scaling correctly
        screenshot = pyautogui.screenshot(region=(left, top, width, height))

        return screenshot

    @staticmethod
    def save_screenshot(image: Image.Image, output_path: Path) -> None:
        """Save image to file, creating directories as needed.

        Args:
            image: PIL Image to save
            output_path: Path where to save the image
        """
        output_path.parent.mkdir(parents=True, exist_ok=True)
        image.save(output_path, 'PNG', optimize=True)
