"""Shared Windows API handles, constants, and callback types."""

import ctypes
from ctypes import wintypes

# Windows API constants
SW_RESTORE = 9
SW_SHOW = 5
SW_MINIMIZE = 6
MONITOR_DEFAULTTONEAREST = 2
SWP_NOSIZE = 0x0001
SWP_NOMOVE = 0x0002
SWP_NOZORDER = 0x0004
SWP_NOACTIVATE = 0x0010
HWND_TOPMOST = -1

# Load Windows DLLs
user32 = ctypes.windll.user32
kernel32 = ctypes.windll.kernel32
dwmapi = ctypes.windll.dwmapi

# DwmGetWindowAttribute returns the visible frame without the resize border.
DWMWA_EXTENDED_FRAME_BOUNDS = 9
dwmapi.DwmGetWindowAttribute.restype = ctypes.c_long
dwmapi.DwmGetWindowAttribute.argtypes = [
    wintypes.HWND,
    wintypes.DWORD,
    ctypes.c_void_p,
    wintypes.DWORD,
]

# EnumWindows passes every top-level window to this callback signature.
_ENUM_WINDOWS_PROC = ctypes.WINFUNCTYPE(wintypes.BOOL, wintypes.HWND, wintypes.LPARAM)
_ENUM_VISIBLE_WINDOWS_PROC = ctypes.WINFUNCTYPE(
    ctypes.c_bool, wintypes.HWND, wintypes.LPARAM
)

# These shell windows must not be minimized during a recording.
_SHELL_CLASSES = frozenset(
    {
        "Progman",
        "WorkerW",
        "Shell_TrayWnd",
        "Shell_SecondaryTrayWnd",
        "Button",
        "NotifyIconOverflowWindow",
        "Windows.UI.Core.CoreWindow",
    }
)

# ShowWindow returns while the shell is still animating windows away.
MINIMIZE_SETTLE_S = 1.2


class _MONITORINFO(ctypes.Structure):
    """Monitor metadata returned by GetMonitorInfoW."""

    _fields_ = [
        ("cbSize", wintypes.DWORD),
        ("rcMonitor", wintypes.RECT),
        ("rcWork", wintypes.RECT),
        ("dwFlags", wintypes.DWORD),
    ]
