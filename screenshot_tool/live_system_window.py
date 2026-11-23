"""Route current-state live operations to an Android system window when needed."""

from __future__ import annotations

from pathlib import Path

from screenshot_tool.app_logger import AppLogger
from screenshot_tool.demo_protocol import DemoEvent
from screenshot_tool.device_screen import DeviceScreen
from screenshot_tool.live_gesture import GestureKind, GestureRequest
from screenshot_tool.live_input import InputKind, InputRequest
from screenshot_tool.live_types import LiveError, ShotRequest

_SYSTEM_WINDOW_ERROR = "operation is not available while a system window is in front"


class SystemWindow:
    """Use adb for gestures and captures while Android owns the foreground window."""

    def __init__(self, screen: DeviceScreen, app_package: str | None) -> None:
        self._screen = screen
        self._app_package = app_package

    def in_front(self) -> bool:
        """Return whether the foreground activity belongs to another package."""
        if self._app_package is None:
            return False
        try:
            package = self._screen.foreground_package()
        except Exception as error:
            AppLogger.warning(f"Could not detect Android foreground activity: {error}")
            return False
        if package is None:
            AppLogger.warning("Could not detect Android foreground activity package")
            return False
        return package != self._app_package

    def gesture(self, request: GestureRequest) -> None:
        """Perform a supported tap or drag on the full Android screen."""
        if request.kind is GestureKind.PINCH or request.screen is not None or request.section:
            raise LiveError(_SYSTEM_WINDOW_ERROR)
        if request.kind is GestureKind.TAP:
            if request.at is None:
                raise LiveError("system-window tap requires coordinates")
            self._screen.tap(*request.at)
            return
        if request.kind is GestureKind.DRAG:
            if request.from_point is None or request.to is None:
                raise LiveError("system-window drag requires start and end coordinates")
            self._screen.swipe(request.from_point, request.to, request.duration_ms)
            return
        raise LiveError(_SYSTEM_WINDOW_ERROR)

    def tap_text(self, request: InputRequest) -> DemoEvent:
        """Tap a visible Android UI label and return the connector's reply shape."""
        if request.kind is not InputKind.TAP_TEXT or request.text is None:
            raise LiveError(_SYSTEM_WINDOW_ERROR)
        self._screen.tap_text(request.text, request.match, request.index)
        return DemoEvent(event=request.kind.reply_event, demo=None, name=None, hwnd=None)

    def shot(self, request: ShotRequest) -> Path:
        """Save a full-device screenshot when no app-specific options were requested."""
        if request.screen is not None or request.theme is not None or request.section is not None:
            raise LiveError(_SYSTEM_WINDOW_ERROR)
        return request.save_png(self._screen.capture_png())
