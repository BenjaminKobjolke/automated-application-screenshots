"""Window visibility, stacking, minimization, and foreground operations."""

import ctypes
import time

from . import win32_api
from .app_logger import AppLogger


class WindowStacking:
    """Provide window stacking and foreground operations."""

    @staticmethod
    def should_minimize(hwnd: int) -> bool:
        """Whether a visible top-level window is safe to minimize."""
        user32 = win32_api.user32
        if not user32.IsWindowVisible(hwnd) or user32.IsIconic(hwnd):
            return False
        if user32.GetWindowTextLengthW(hwnd) <= 0:
            return False
        name = ctypes.create_unicode_buffer(256)
        user32.GetClassNameW(hwnd, name, len(name))
        return name.value not in win32_api._SHELL_CLASSES

    @staticmethod
    def minimize_all() -> int:
        """Minimize visible top-level windows and let the shell settle."""
        minimized = 0

        def visit(hwnd: int, _param: int) -> bool:
            nonlocal minimized
            if WindowStacking.should_minimize(hwnd):
                win32_api.user32.ShowWindow(hwnd, win32_api.SW_MINIMIZE)
                minimized += 1
            return True

        win32_api.user32.EnumWindows(win32_api._ENUM_WINDOWS_PROC(visit), 0)
        AppLogger.info(f"Minimized {minimized} window(s) before recording.")
        time.sleep(win32_api.MINIMIZE_SETTLE_S)
        return minimized

    @staticmethod
    def set_topmost(hwnd: int) -> None:
        """Raise a window above other windows without activating it."""
        win32_api.user32.SetWindowPos(
            hwnd,
            win32_api.HWND_TOPMOST,
            0,
            0,
            0,
            0,
            win32_api.SWP_NOMOVE | win32_api.SWP_NOSIZE | win32_api.SWP_NOACTIVATE,
        )

    @staticmethod
    def bring_to_foreground(hwnd: int) -> bool:
        """Restore a minimized window and bring it to the foreground."""
        user32 = win32_api.user32
        user32.ShowWindow(hwnd, win32_api.SW_RESTORE if user32.IsIconic(hwnd) else win32_api.SW_SHOW)
        user32.SetForegroundWindow(hwnd)
        return True
