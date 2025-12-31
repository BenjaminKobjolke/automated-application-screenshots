"""Windows API integration for finding application windows."""

import ctypes
from ctypes import wintypes
import psutil

# Windows API constants
SW_RESTORE = 9
SW_SHOW = 5

# Load Windows DLLs
user32 = ctypes.windll.user32
kernel32 = ctypes.windll.kernel32


class WindowFinder:
    """Find Windows application windows using various strategies."""

    @staticmethod
    def find_by_process_name(process_name: str) -> int | None:
        """Find main window handle by process name.

        Args:
            process_name: The executable name (e.g., "app.exe")

        Returns:
            Window handle (HWND) or None if not found
        """
        for proc in psutil.process_iter(['pid', 'name']):
            if proc.info['name'] and proc.info['name'].lower() == process_name.lower():
                pid = proc.info['pid']
                hwnd = WindowFinder._get_window_by_pid(pid)
                if hwnd:
                    return hwnd
        return None

    @staticmethod
    def find_by_title_substring(substring: str) -> int | None:
        """Find window handle by title containing substring.

        Args:
            substring: Text that should be in the window title

        Returns:
            Window handle (HWND) or None if not found
        """
        result = []

        def enum_callback(hwnd, _):
            if user32.IsWindowVisible(hwnd):
                length = user32.GetWindowTextLengthW(hwnd)
                if length > 0:
                    buffer = ctypes.create_unicode_buffer(length + 1)
                    user32.GetWindowTextW(hwnd, buffer, length + 1)
                    title = buffer.value
                    if substring.lower() in title.lower():
                        result.append(hwnd)
            return True

        enum_func = ctypes.WINFUNCTYPE(ctypes.c_bool, wintypes.HWND, wintypes.LPARAM)
        user32.EnumWindows(enum_func(enum_callback), 0)

        return result[0] if result else None

    @staticmethod
    def _get_window_by_pid(pid: int) -> int | None:
        """Get main window handle for a process ID.

        Args:
            pid: Process ID

        Returns:
            Window handle (HWND) or None if not found
        """
        result = []

        def enum_callback(hwnd, _):
            if user32.IsWindowVisible(hwnd):
                window_pid = wintypes.DWORD()
                user32.GetWindowThreadProcessId(hwnd, ctypes.byref(window_pid))
                if window_pid.value == pid:
                    # Check if it's a main window (has a title)
                    length = user32.GetWindowTextLengthW(hwnd)
                    if length > 0:
                        result.append(hwnd)
            return True

        enum_func = ctypes.WINFUNCTYPE(ctypes.c_bool, wintypes.HWND, wintypes.LPARAM)
        user32.EnumWindows(enum_func(enum_callback), 0)

        return result[0] if result else None

    @staticmethod
    def get_window_rect(hwnd: int) -> tuple[int, int, int, int]:
        """Get window rectangle (left, top, right, bottom).

        Args:
            hwnd: Window handle

        Returns:
            Tuple of (left, top, right, bottom) coordinates
        """
        rect = wintypes.RECT()
        user32.GetWindowRect(hwnd, ctypes.byref(rect))
        return (rect.left, rect.top, rect.right, rect.bottom)

    @staticmethod
    def get_window_title(hwnd: int) -> str:
        """Get window title text.

        Args:
            hwnd: Window handle

        Returns:
            Window title string
        """
        length = user32.GetWindowTextLengthW(hwnd)
        if length > 0:
            buffer = ctypes.create_unicode_buffer(length + 1)
            user32.GetWindowTextW(hwnd, buffer, length + 1)
            return buffer.value
        return ""

    @staticmethod
    def bring_to_foreground(hwnd: int) -> bool:
        """Bring window to foreground and restore if minimized.

        Args:
            hwnd: Window handle

        Returns:
            True if successful
        """
        # Check if minimized
        if user32.IsIconic(hwnd):
            user32.ShowWindow(hwnd, SW_RESTORE)
        else:
            user32.ShowWindow(hwnd, SW_SHOW)

        # Bring to foreground
        user32.SetForegroundWindow(hwnd)
        return True

    @staticmethod
    def is_window_valid(hwnd: int) -> bool:
        """Check if window handle is still valid.

        Args:
            hwnd: Window handle

        Returns:
            True if window exists and is valid
        """
        return bool(user32.IsWindow(hwnd))
