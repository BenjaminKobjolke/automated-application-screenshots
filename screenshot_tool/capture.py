"""Window capture: PrintWindow first, screen-region grab as fallback.

PrintWindow with PW_RENDERFULLCONTENT renders the window itself through DWM, so
frames stay correct while Windows is locked and other windows cannot bleed in.
When PrintWindow fails, capture falls back to a pyautogui grab of the window's
screen rectangle; that path needs the window topmost, which `demo_cli` ensures.
"""

import ctypes
from contextlib import suppress
from ctypes import wintypes
from pathlib import Path

import pyautogui
from PIL import Image

from . import win32_api
from .window_geometry import WindowGeometry

# Enable DPI awareness for accurate window positioning
try:
    ctypes.windll.shcore.SetProcessDpiAwareness(2)  # PROCESS_PER_MONITOR_DPI_AWARE
except Exception:
    with suppress(Exception):
        ctypes.windll.user32.SetProcessDPIAware()


def _print_window(hwnd: int, size: tuple[int, int]) -> Image.Image | None:
    """Render the whole window rect (size = width, height) via PrintWindow; None on failure."""
    width, height = size
    user32, gdi32 = win32_api.user32, win32_api.gdi32
    window_dc = user32.GetWindowDC(hwnd)
    memory_dc = gdi32.CreateCompatibleDC(window_dc)
    bitmap = gdi32.CreateCompatibleBitmap(window_dc, width, height)
    try:
        gdi32.SelectObject(memory_dc, bitmap)
        if not user32.PrintWindow(hwnd, memory_dc, win32_api.PW_RENDERFULLCONTENT):
            return None
        pixels = ctypes.create_string_buffer(width * height * 4)
        gdi32.GetBitmapBits(bitmap, len(pixels), pixels)
        return Image.frombuffer("RGB", size, pixels, "raw", "BGRX", 0, 1)
    finally:
        gdi32.DeleteObject(bitmap)
        gdi32.DeleteDC(memory_dc)
        user32.ReleaseDC(hwnd, window_dc)


def _process_id(hwnd: int) -> int:
    pid = wintypes.DWORD()
    win32_api.user32.GetWindowThreadProcessId(hwnd, ctypes.byref(pid))
    return pid.value


def _windows_above(hwnd: int) -> list[int]:
    """Visible windows of the same process above hwnd in z-order, nearest first.

    Dialogs and popups (e.g. a quick-search QDialog) are separate top-level
    windows, so PrintWindow of the main window alone would leave them out.
    """
    pid = _process_id(hwnd)
    above = []
    current = win32_api.user32.GetWindow(hwnd, win32_api.GW_HWNDPREV)
    while current:
        if win32_api.user32.IsWindowVisible(current) and _process_id(current) == pid:
            above.append(current)
        current = win32_api.user32.GetWindow(current, win32_api.GW_HWNDPREV)
    return above


def _render_window_stack(hwnd: int) -> Image.Image | None:
    """PrintWindow hwnd plus its process's windows above it, in hwnd's window-rect space."""
    rect = WindowGeometry.get_window_rect(hwnd)
    image = _print_window(hwnd, (rect[2] - rect[0], rect[3] - rect[1]))
    if image is None:
        return None
    for window in reversed(_windows_above(hwnd)):
        left, top, right, bottom = WindowGeometry.get_window_rect(window)
        layer = _print_window(window, (right - left, bottom - top))
        if layer is not None:
            image.paste(layer, (left - rect[0], top - rect[1]))
    return image


class WindowCapture:
    """Capture screenshots of Windows application windows."""

    @staticmethod
    def capture_window(hwnd: int) -> Image.Image:
        """Capture a window's visible frame and return it as a PIL Image.

        Uses PrintWindow, so a locked desktop or covering window does not matter;
        falls back to a pyautogui screen-region grab when PrintWindow fails.

        Args:
            hwnd: Window handle to capture

        Returns:
            PIL Image of the window

        Raises:
            RuntimeError: If capture fails
        """
        # Real visible bounds (no invisible DWM border), clamped to the work area
        # so the taskbar can't appear even when the window overlaps it.
        left, top, right, bottom = WindowGeometry.get_extended_frame_bounds(hwnd)
        work = WindowGeometry.get_work_area(hwnd)
        if work is not None:
            left, top = max(left, work[0]), max(top, work[1])
            right, bottom = min(right, work[2]), min(bottom, work[3])
        width = right - left
        height = bottom - top

        if width <= 0 or height <= 0:
            raise RuntimeError(f"Invalid window dimensions: {width}x{height}")

        rendered = _render_window_stack(hwnd)
        if rendered is not None:
            rect = WindowGeometry.get_window_rect(hwnd)
            return rendered.crop(
                (left - rect[0], top - rect[1], right - rect[0], bottom - rect[1])
            )

        # Screen-region grab handles DPI scaling correctly but needs an unlocked desktop
        return pyautogui.screenshot(region=(left, top, width, height))

    @staticmethod
    def save_screenshot(image: Image.Image, output_path: Path) -> None:
        """Save image to file, creating directories as needed.

        Args:
            image: PIL Image to save
            output_path: Path where to save the image
        """
        output_path.parent.mkdir(parents=True, exist_ok=True)
        image.save(output_path, "PNG", optimize=True)
