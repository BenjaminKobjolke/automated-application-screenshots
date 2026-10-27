"""Windows API integration for finding application windows."""

import ctypes
from ctypes import wintypes

import psutil

from . import win32_api
from .window_geometry import clamp_to_work_area

__all__ = ["WindowFinder", "clamp_to_work_area"]


class WindowFinder:
    """Find Windows application windows and bring them to the foreground."""

    @staticmethod
    def _find_visible_window(predicate) -> int | None:
        """Return the first visible top-level window accepted by predicate."""
        result: list[int] = []

        def enum_callback(hwnd, _):
            if win32_api.user32.IsWindowVisible(hwnd) and predicate(hwnd):
                result.append(hwnd)
            return True

        win32_api.user32.EnumWindows(win32_api._ENUM_VISIBLE_WINDOWS_PROC(enum_callback), 0)
        return result[0] if result else None

    @staticmethod
    def find_by_process_name(process_name: str) -> int | None:
        """Find main window handle by process name."""
        for proc in psutil.process_iter(["pid", "name"]):
            if proc.info["name"] and proc.info["name"].lower() == process_name.lower():
                hwnd = WindowFinder.find_by_pid(proc.info["pid"])
                if hwnd:
                    return hwnd
        return None

    @staticmethod
    def find_by_title_substring(substring: str) -> int | None:
        """Find a visible window whose title contains the given text."""
        return WindowFinder._find_visible_window(
            lambda hwnd: substring.lower() in WindowFinder.get_window_title(hwnd).lower()
        )

    @staticmethod
    def find_by_pid(pid: int) -> int | None:
        """Get the main window handle for a process ID."""

        def belongs_to_pid(hwnd: int) -> bool:
            window_pid = wintypes.DWORD()
            win32_api.user32.GetWindowThreadProcessId(hwnd, ctypes.byref(window_pid))
            return window_pid.value == pid and WindowFinder.get_window_title(hwnd) != ""

        return WindowFinder._find_visible_window(belongs_to_pid)

    @staticmethod
    def get_window_title(hwnd: int) -> str:
        """Get window title text."""
        user32 = win32_api.user32
        length = user32.GetWindowTextLengthW(hwnd)
        if length > 0:
            buffer = ctypes.create_unicode_buffer(length + 1)
            user32.GetWindowTextW(hwnd, buffer, length + 1)
            return buffer.value
        return ""

    @staticmethod
    def is_window_valid(hwnd: int) -> bool:
        """Check whether a window handle is still valid."""
        return bool(win32_api.user32.IsWindow(hwnd))

    @staticmethod
    def bring_to_foreground(hwnd: int) -> bool:
        """Restore a minimized window and bring it to the foreground."""
        user32 = win32_api.user32
        command = win32_api.SW_RESTORE if user32.IsIconic(hwnd) else win32_api.SW_SHOW
        user32.ShowWindow(hwnd, command)
        user32.SetForegroundWindow(hwnd)
        return True
