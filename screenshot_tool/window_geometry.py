"""Window rectangles and monitor work-area operations."""

import ctypes
from ctypes import wintypes

from . import win32_api
from .app_logger import AppLogger


def clamp_to_work_area(
    window_rect: tuple[int, int, int, int], work_rect: tuple[int, int, int, int]
) -> tuple[int, int]:
    """Return the top-left position that keeps a window inside the work area.

    Shifts the window the minimal distance so it does not extend under the
    taskbar or off a work-area edge. A larger window is pinned to the top-left.
    """
    win_left, win_top, win_right, win_bottom = window_rect
    work_left, work_top, work_right, work_bottom = work_rect
    width = win_right - win_left
    height = win_bottom - win_top
    x = min(win_left, work_right - width)
    y = min(win_top, work_bottom - height)
    return (max(x, work_left), max(y, work_top))


class WindowGeometry:
    """Provide work-area and rectangle operations for a window finder."""

    @staticmethod
    def get_window_rect(hwnd: int) -> tuple[int, int, int, int]:
        """Get window rectangle (left, top, right, bottom)."""
        rect = wintypes.RECT()
        win32_api.user32.GetWindowRect(hwnd, ctypes.byref(rect))
        return (rect.left, rect.top, rect.right, rect.bottom)

    @staticmethod
    def get_extended_frame_bounds(hwnd: int) -> tuple[int, int, int, int]:
        """Get visible frame bounds, falling back to GetWindowRect on failure."""
        rect = wintypes.RECT()
        hr = win32_api.dwmapi.DwmGetWindowAttribute(
            wintypes.HWND(hwnd),
            win32_api.DWMWA_EXTENDED_FRAME_BOUNDS,
            ctypes.byref(rect),
            ctypes.sizeof(rect),
        )
        if hr != 0:
            return WindowGeometry.get_window_rect(hwnd)
        return (rect.left, rect.top, rect.right, rect.bottom)

    @staticmethod
    def get_work_area(hwnd: int) -> tuple[int, int, int, int] | None:
        """Get the work area for the window's monitor, or None on query failure."""
        monitor = win32_api.user32.MonitorFromWindow(
            hwnd, win32_api.MONITOR_DEFAULTTONEAREST
        )
        info = win32_api._MONITORINFO()
        info.cbSize = ctypes.sizeof(win32_api._MONITORINFO)
        if not win32_api.user32.GetMonitorInfoW(monitor, ctypes.byref(info)):
            return None
        return (info.rcWork.left, info.rcWork.top, info.rcWork.right, info.rcWork.bottom)

    @staticmethod
    def move_into_work_area(hwnd: int) -> None:
        """Move a window inside its monitor's work area when necessary."""
        monitor = win32_api.user32.MonitorFromWindow(
            hwnd, win32_api.MONITOR_DEFAULTTONEAREST
        )
        info = win32_api._MONITORINFO()
        info.cbSize = ctypes.sizeof(win32_api._MONITORINFO)
        if not win32_api.user32.GetMonitorInfoW(monitor, ctypes.byref(info)):
            AppLogger.warning(f"GetMonitorInfo failed for hwnd {hwnd}; window not moved.")
            return
        work = (info.rcWork.left, info.rcWork.top, info.rcWork.right, info.rcWork.bottom)
        rect = WindowGeometry.get_window_rect(hwnd)
        if rect[2] - rect[0] > work[2] - work[0] or rect[3] - rect[1] > work[3] - work[1]:
            AppLogger.warning(
                f"Window {rect} is larger than the monitor work area {work}; "
                "the taskbar may still overlap the capture."
            )
        x, y = clamp_to_work_area(rect, work)
        if (x, y) != (rect[0], rect[1]):
            AppLogger.info(f"Moving window from ({rect[0]}, {rect[1]}) to ({x}, {y})")
            win32_api.user32.SetWindowPos(
                hwnd,
                0,
                x,
                y,
                0,
                0,
                win32_api.SWP_NOSIZE | win32_api.SWP_NOZORDER | win32_api.SWP_NOACTIVATE,
            )
