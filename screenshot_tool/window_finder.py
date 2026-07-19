"""Windows API integration for finding application windows."""

import ctypes
from ctypes import wintypes
import psutil

from .app_logger import AppLogger

# Windows API constants
SW_RESTORE = 9
SW_SHOW = 5
MONITOR_DEFAULTTONEAREST = 2
SWP_NOSIZE = 0x0001
SWP_NOZORDER = 0x0004
SWP_NOACTIVATE = 0x0010

# Load Windows DLLs
user32 = ctypes.windll.user32
kernel32 = ctypes.windll.kernel32


class _MONITORINFO(ctypes.Structure):
    _fields_ = [
        ("cbSize", wintypes.DWORD),
        ("rcMonitor", wintypes.RECT),
        ("rcWork", wintypes.RECT),
        ("dwFlags", wintypes.DWORD),
    ]


def clamp_to_work_area(
    window_rect: tuple[int, int, int, int], work_rect: tuple[int, int, int, int]
) -> tuple[int, int]:
    """Top-left position that keeps the window inside the monitor work area.

    Shifts the window the minimal distance so it does not extend under the
    taskbar (or off any work-area edge). A window larger than the work area
    is pinned to the work area's top-left.

    Args:
        window_rect: Window (left, top, right, bottom)
        work_rect: Monitor work area (left, top, right, bottom)

    Returns:
        Clamped (x, y); equals the current position when already inside.
    """
    win_left, win_top, win_right, win_bottom = window_rect
    work_left, work_top, work_right, work_bottom = work_rect
    width = win_right - win_left
    height = win_bottom - win_top
    x = min(win_left, work_right - width)
    y = min(win_top, work_bottom - height)
    return (max(x, work_left), max(y, work_top))


class WindowFinder:
    """Find Windows application windows using various strategies."""

    @staticmethod
    def _find_visible_window(predicate) -> int | None:
        """Enumerate visible top-level windows and return the first matching one.

        Args:
            predicate: Callable taking a window handle, returning True on match

        Returns:
            Window handle (HWND) or None if not found
        """
        result: list[int] = []

        def enum_callback(hwnd, _):
            if user32.IsWindowVisible(hwnd) and predicate(hwnd):
                result.append(hwnd)
            return True

        enum_func = ctypes.WINFUNCTYPE(ctypes.c_bool, wintypes.HWND, wintypes.LPARAM)
        user32.EnumWindows(enum_func(enum_callback), 0)

        return result[0] if result else None

    @staticmethod
    def find_by_process_name(process_name: str) -> int | None:
        """Find main window handle by process name.

        Args:
            process_name: The executable name (e.g., "app.exe")

        Returns:
            Window handle (HWND) or None if not found
        """
        for proc in psutil.process_iter(["pid", "name"]):
            if proc.info["name"] and proc.info["name"].lower() == process_name.lower():
                pid = proc.info["pid"]
                hwnd = WindowFinder.find_by_pid(pid)
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
        return WindowFinder._find_visible_window(
            lambda hwnd: substring.lower() in WindowFinder.get_window_title(hwnd).lower()
        )

    @staticmethod
    def find_by_pid(pid: int) -> int | None:
        """Get main window handle for a process ID.

        Args:
            pid: Process ID

        Returns:
            Window handle (HWND) or None if not found
        """

        def belongs_to_pid(hwnd: int) -> bool:
            window_pid = wintypes.DWORD()
            user32.GetWindowThreadProcessId(hwnd, ctypes.byref(window_pid))
            # Titleless windows are not main windows
            return window_pid.value == pid and WindowFinder.get_window_title(hwnd) != ""

        return WindowFinder._find_visible_window(belongs_to_pid)

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
    def move_into_work_area(hwnd: int) -> None:
        """Move the window so it stays inside its monitor's work area.

        Prevents the always-on-top taskbar from overlapping the window
        (and thus appearing in screen captures of its rect).

        Args:
            hwnd: Window handle
        """
        monitor = user32.MonitorFromWindow(hwnd, MONITOR_DEFAULTTONEAREST)
        info = _MONITORINFO()
        info.cbSize = ctypes.sizeof(_MONITORINFO)
        if not user32.GetMonitorInfoW(monitor, ctypes.byref(info)):
            AppLogger.warning(f"GetMonitorInfo failed for hwnd {hwnd}; window not moved.")
            return
        work = (info.rcWork.left, info.rcWork.top, info.rcWork.right, info.rcWork.bottom)
        rect = WindowFinder.get_window_rect(hwnd)
        if rect[2] - rect[0] > work[2] - work[0] or rect[3] - rect[1] > work[3] - work[1]:
            AppLogger.warning(
                f"Window {rect} is larger than the monitor work area {work}; "
                "the taskbar may still overlap the capture."
            )
        x, y = clamp_to_work_area(rect, work)
        if (x, y) != (rect[0], rect[1]):
            AppLogger.info(f"Moving window from ({rect[0]}, {rect[1]}) to ({x}, {y})")
            user32.SetWindowPos(hwnd, 0, x, y, 0, 0, SWP_NOSIZE | SWP_NOZORDER | SWP_NOACTIVATE)

    @staticmethod
    def is_window_valid(hwnd: int) -> bool:
        """Check if window handle is still valid.

        Args:
            hwnd: Window handle

        Returns:
            True if window exists and is valid
        """
        return bool(user32.IsWindow(hwnd))
