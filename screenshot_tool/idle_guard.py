"""Warn someone who is working before capture takes over mouse, focus and windows."""

import ctypes
import tkinter
from typing import TYPE_CHECKING

from .app_logger import AppLogger
from .win32_api import _LASTINPUTINFO, kernel32, user32

if TYPE_CHECKING:
    from .live_config import LiveSettings
    from .web_config import WebSettings

IDLE_THRESHOLD_S = 60
COUNTDOWN_S = 10


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
    root.update_idletasks()
    x = (root.winfo_screenwidth() - root.winfo_reqwidth()) // 2
    y = (root.winfo_screenheight() - root.winfo_reqheight()) // 2
    root.geometry(f"+{x}+{y}")
    root.mainloop()


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


def warn_if_active() -> None:
    """Give an active user time to get out of the way before capture starts."""
    if seconds_since_input() >= IDLE_THRESHOLD_S:
        return

    AppLogger.info(
        "Recent keyboard or mouse activity detected; showing a 10-second start warning"
    )
    try:
        show_countdown(COUNTDOWN_S)
    except tkinter.TclError as error:
        AppLogger.warning(f"Could not show the start warning window; continuing: {error}")
