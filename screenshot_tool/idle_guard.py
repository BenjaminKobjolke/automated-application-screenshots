"""Show start and end alerts around captures that interrupt an active user."""

import ctypes
import subprocess
import sys
import tkinter
from typing import TYPE_CHECKING

from . import win32_api
from .app_logger import AppLogger
from .win32_api import _LASTINPUTINFO, kernel32, user32
from .window_finder import WindowFinder

if TYPE_CHECKING:
    from .live_config import LiveSettings
    from .web_config import WebSettings

IDLE_THRESHOLD_S = 60
COUNTDOWN_S = 10
DONE_TITLE = "Screenshots finished"
DONE_MESSAGE = "Screenshots are finished — you can use the PC again."
TK_WINDOW_CLASS = "TkTopLevel"


def _is_leftover_alert(title: str, class_name: str) -> bool:
    """Match only the completion alert owned by this tool."""
    return title == DONE_TITLE and class_name == TK_WINDOW_CLASS


def close_leftover_alerts() -> int:
    """Close this tool's topmost completion alerts left by previous runs."""
    matches: list[int] = []

    def visit(hwnd: int, _param: int) -> bool:
        class_buffer = ctypes.create_unicode_buffer(256)
        win32_api.user32.GetClassNameW(hwnd, class_buffer, len(class_buffer))
        title = WindowFinder.get_window_title(hwnd)
        if _is_leftover_alert(title, class_buffer.value):
            matches.append(hwnd)
        return True

    win32_api.user32.EnumWindows(win32_api._ENUM_WINDOWS_PROC(visit), 0)

    closed = 0
    for hwnd in matches:
        result = win32_api.DWORD_PTR()
        succeeded = win32_api.user32.SendMessageTimeoutW(
            hwnd,
            win32_api.WM_CLOSE,
            0,
            0,
            win32_api.SMTO_ABORTIFHUNG,
            win32_api.ALERT_CLOSE_TIMEOUT_MS,
            ctypes.byref(result),
        )
        if succeeded:
            closed += 1
        else:
            AppLogger.warning(f"Could not close leftover end-of-run alert (window {hwnd})")

    if closed > 0:
        AppLogger.info(f"Closed {closed} leftover end-of-run alert(s)")
    return closed


def seconds_since_input() -> float:
    """Return the seconds since Windows last received keyboard or mouse input."""
    last_input = _LASTINPUTINFO()
    last_input.cbSize = ctypes.sizeof(_LASTINPUTINFO)
    if not user32.GetLastInputInfo(ctypes.byref(last_input)):
        raise ctypes.WinError()

    elapsed_ms = (kernel32.GetTickCount() - last_input.dwTime) & 0xFFFFFFFF
    return elapsed_ms / 1000


def show_countdown(seconds: int) -> None:
    """Show a topmost countdown that can be ended by the user or its timer."""
    root = tkinter.Tk()
    root.title("Screenshots are about to start")
    root.attributes("-topmost", True)

    def finish() -> None:
        if root.winfo_exists():
            root.destroy()
            root.update()

    label = tkinter.Label(root, wraplength=420, padx=24, pady=16)
    label.pack()
    tkinter.Button(root, text="Start now", command=finish, padx=12, pady=6).pack(
        pady=(0, 16)
    )

    remaining = seconds

    def tick() -> None:
        nonlocal remaining
        message = f"Screenshots start in {remaining} s — please leave mouse and keyboard alone"
        label.config(text=message)
        if remaining <= 0:
            finish()
            return
        remaining -= 1
        root.after(1000, tick)

    root.protocol("WM_DELETE_WINDOW", finish)
    tick()
    _center(root)
    root.mainloop()


def show_done_alert() -> None:
    """Show a topmost completion alert until the user closes it."""
    root = tkinter.Tk()
    root.title(DONE_TITLE)
    root.attributes("-topmost", True)
    tkinter.Label(root, text=DONE_MESSAGE, wraplength=420, padx=24, pady=16).pack()
    tkinter.Button(root, text="OK", command=root.destroy, padx=12, pady=6).pack(
        pady=(0, 16)
    )
    root.protocol("WM_DELETE_WINDOW", root.destroy)
    _center(root)
    root.mainloop()


def _center(root: tkinter.Tk) -> None:
    """Center a prepared alert window on the screen."""
    root.update_idletasks()
    x = (root.winfo_screenwidth() - root.winfo_reqwidth()) // 2
    y = (root.winfo_screenheight() - root.winfo_reqheight()) // 2
    root.geometry(f"+{x}+{y}")


def notify_done() -> None:
    """Launch the persistent completion alert without blocking the CLI."""
    AppLogger.info("Showing the end-of-run alert because the start warning was shown")
    try:
        # The CLI must not wait for someone to click OK.
        subprocess.Popen(
            [
                sys.executable,
                "-c",
                "from screenshot_tool.idle_guard import show_done_alert; show_done_alert()",
            ],
            creationflags=subprocess.DETACHED_PROCESS | subprocess.CREATE_NEW_PROCESS_GROUP,
            close_fds=True,
        )
    except OSError as error:
        AppLogger.warning(f"Could not show the end-of-run alert; continuing: {error}")


def shows_windows(
    *,
    list_mode: bool,
    demo: bool,
    compose: bool,
    live: bool,
    live_settings: "LiveSettings | None",
    web_settings: "WebSettings | None",
) -> bool:
    """Return whether this CLI invocation will show a capture window on screen."""
    if list_mode or (compose and not demo):
        return False

    if live:
        from .live_config import LiveTarget

        return not (
            live_settings is not None
            and live_settings.target is LiveTarget.ANDROID_EMULATOR
            and live_settings.headless
        )

    if demo:
        return True

    if web_settings is not None:
        return not web_settings.headless

    return True


def warn_if_active() -> bool:
    """Give an active user time to get out of the way and report whether shown."""
    if seconds_since_input() >= IDLE_THRESHOLD_S:
        return False

    AppLogger.info(
        "Recent keyboard or mouse activity detected; showing a 10-second start warning"
    )
    try:
        show_countdown(COUNTDOWN_S)
    except tkinter.TclError as error:
        AppLogger.warning(f"Could not show the start warning window; continuing: {error}")
        return False
    return True
