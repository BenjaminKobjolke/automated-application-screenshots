"""Shared Windows API handles, constants, and callback types."""

import ctypes
from ctypes import wintypes
from typing import ClassVar

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
WM_CLOSE = 0x0010
SMTO_ABORTIFHUNG = 0x0002
ALERT_CLOSE_TIMEOUT_MS = 2000

# ctypes.wintypes omits these pointer-sized Windows aliases on supported Python versions.
DWORD_PTR = ctypes.c_size_t
LRESULT = ctypes.c_ssize_t

# Load Windows DLLs
user32 = ctypes.windll.user32
kernel32 = ctypes.windll.kernel32
dwmapi = ctypes.windll.dwmapi
gdi32 = ctypes.windll.gdi32

# PrintWindow flag: render through DWM, so it works while the desktop is locked.
PW_RENDERFULLCONTENT = 2
GW_HWNDPREV = 3
user32.GetWindow.restype = wintypes.HWND
user32.GetWindow.argtypes = [wintypes.HWND, wintypes.UINT]
user32.GetClassNameW.restype = ctypes.c_int
user32.GetClassNameW.argtypes = [wintypes.HWND, wintypes.LPWSTR, ctypes.c_int]
user32.GetWindowTextLengthW.restype = ctypes.c_int
user32.GetWindowTextLengthW.argtypes = [wintypes.HWND]
user32.GetWindowTextW.restype = ctypes.c_int
user32.GetWindowTextW.argtypes = [wintypes.HWND, wintypes.LPWSTR, ctypes.c_int]
user32.SendMessageTimeoutW.restype = LRESULT
user32.SendMessageTimeoutW.argtypes = [
    wintypes.HWND,
    wintypes.UINT,
    wintypes.WPARAM,
    wintypes.LPARAM,
    wintypes.UINT,
    wintypes.UINT,
    ctypes.POINTER(DWORD_PTR),
]
# Handle-returning calls default to a 32-bit int restype, which truncates 64-bit handles.
user32.GetWindowDC.restype = wintypes.HDC
user32.GetWindowDC.argtypes = [wintypes.HWND]
user32.ReleaseDC.argtypes = [wintypes.HWND, wintypes.HDC]
user32.PrintWindow.argtypes = [wintypes.HWND, wintypes.HDC, wintypes.UINT]
gdi32.CreateCompatibleDC.restype = wintypes.HDC
gdi32.CreateCompatibleDC.argtypes = [wintypes.HDC]
gdi32.CreateCompatibleBitmap.restype = wintypes.HBITMAP
gdi32.CreateCompatibleBitmap.argtypes = [wintypes.HDC, ctypes.c_int, ctypes.c_int]
gdi32.SelectObject.restype = wintypes.HGDIOBJ
gdi32.SelectObject.argtypes = [wintypes.HDC, wintypes.HGDIOBJ]
gdi32.GetBitmapBits.argtypes = [wintypes.HBITMAP, wintypes.LONG, ctypes.c_void_p]
gdi32.DeleteObject.argtypes = [wintypes.HGDIOBJ]
gdi32.DeleteDC.argtypes = [wintypes.HDC]

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

    _fields_: ClassVar = [
        ("cbSize", wintypes.DWORD),
        ("rcMonitor", wintypes.RECT),
        ("rcWork", wintypes.RECT),
        ("dwFlags", wintypes.DWORD),
    ]


class _LASTINPUTINFO(ctypes.Structure):
    """Last keyboard or mouse input timestamp returned by Windows."""

    _fields_: ClassVar = [
        ("cbSize", wintypes.UINT),
        ("dwTime", wintypes.DWORD),
    ]


user32.GetLastInputInfo.argtypes = [ctypes.POINTER(_LASTINPUTINFO)]
user32.GetLastInputInfo.restype = wintypes.BOOL
kernel32.GetTickCount.restype = wintypes.DWORD
