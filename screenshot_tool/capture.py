"""Screenshot capture logic using pyautogui for reliable cross-DPI capture.

Capture is a screen-region grab of the window's rectangle, so the window must be
the topmost thing at those coordinates when a frame is taken. `demo_cli` raises
the target window to topmost and waits for any previous run's window to close
before recording, so nothing else can bleed into the frame.
"""

import ctypes
from pathlib import Path

import pyautogui
from PIL import Image

from .window_finder import WindowFinder

# Enable DPI awareness for accurate window positioning
try:
    ctypes.windll.shcore.SetProcessDpiAwareness(2)  # PROCESS_PER_MONITOR_DPI_AWARE
except Exception:
    try:
        ctypes.windll.user32.SetProcessDPIAware()
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
        # Real visible bounds (no invisible DWM border), clamped to the work area
        # so the taskbar can't appear even when the window overlaps it.
        left, top, right, bottom = WindowFinder.get_extended_frame_bounds(hwnd)
        work = WindowFinder.get_work_area(hwnd)
        if work is not None:
            left, top = max(left, work[0]), max(top, work[1])
            right, bottom = min(right, work[2]), min(bottom, work[3])
        width = right - left
        height = bottom - top

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
        image.save(output_path, "PNG", optimize=True)
