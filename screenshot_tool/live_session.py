"""Coordinate a Flutter process and its app-side automation connection."""

from __future__ import annotations

from contextlib import nullcontext
from dataclasses import replace
from pathlib import Path
from typing import Any

from .android_emulator import AndroidEmulator
from .demo_protocol import DemoEvent
from .demo_server import DemoServer, ScreenInfo
from .flutter_daemon import FlutterDaemon
from .live_app_link import LiveAppLink
from .live_config import LiveSettings, LiveTarget, device_id
from .live_gesture import GestureRequest, build_gesture_payload
from .live_input import InputKind, InputRequest, build_input_payload
from .live_session_workflows import (
    capture_shot,
    prepare_device,
    recover_named_android_shot,
    relaunch_session,
    reload_session,
    track_app_package,
    wait_for_app_start,
)
from .live_system_window import SystemWindow
from .live_types import (
    LiveConnectionLost,
    LiveError,
    LiveFlutterExited,
    ReloadOutcome,
    ReloadResult,
    ShotOrientation,
    ShotRequest,
    ShotTheme,
)

_COMMAND_TIMEOUT = 60.0

__all__ = ["LiveError", "LiveSession", "ReloadOutcome", "ReloadResult",
           "ShotOrientation", "ShotRequest", "ShotTheme"]


class LiveSession:
    """Own the app connection, Flutter process, and optional emulator lifecycle."""

    def __init__(
        self,
        settings: LiveSettings,
        server: DemoServer | None = None,
        daemon: FlutterDaemon | None = None,
        emulator: AndroidEmulator | None = None,
        log_dir: Path | None = None,
    ) -> None:
        self.settings = settings
        self.server = server if server is not None else DemoServer(port=settings.port)
        self.daemon = daemon if daemon is not None else FlutterDaemon(settings)
        self.app_link = LiveAppLink(self.server, self.daemon)
        if emulator is not None:
            self.emulator = emulator
        elif settings.target is LiveTarget.ANDROID_EMULATOR:
            self.emulator = AndroidEmulator(log_dir=log_dir)
        else:
            self.emulator = None
        self._device: str | None = None
        self._started = False
        self._system_window: SystemWindow | None = None

    def start(self) -> str:
        """Start or reuse the device, launch Flutter, and reset the connected app."""
        if self._started:
            raise LiveError("live session is already started")
        try:
            if self.settings.target is LiveTarget.ANDROID_EMULATOR:
                assert self.emulator is not None
                serial = self.emulator.ensure(
                    self.settings.avd,
                    self.settings.headless,
                    float(self.settings.start_timeout),
                )
                self._device = device_id(self.settings.target, serial)
            else:
                self._device = device_id(self.settings.target)
            prepare_device(self.settings, self.emulator)
            self.daemon.start(self._device)
            wait_for_app_start(self.daemon, self.settings)
            self.app_link.accept_and_reset(self.settings, float(self.settings.start_timeout))
            self._track_app_package()
            self._started = True
            return self._device
        except Exception as error:
            output = self.daemon.output
            self.stop()
            if isinstance(error, LiveError):
                raise
            raise LiveError(f"live start failed: {error}", output) from error

    def reload(self) -> ReloadResult:
        """Hot reload, falling back to hot restart and then a new Flutter run."""
        self._require_started()
        return reload_session(self, _COMMAND_TIMEOUT)

    def screens(self) -> tuple[ScreenInfo, ...]:
        """Ask the app for its registered screens."""
        self._require_started()
        event = self.app_link.request({"command": "list_screens"}, "screens", _COMMAND_TIMEOUT)
        return event.screens or ()

    def device_state(self) -> str | None:
        """Describe the Android emulator when this session has one."""
        if self.settings.target is not LiveTarget.ANDROID_EMULATOR or self.emulator is None:
            return None
        return self.emulator.device_state()

    def reset(self, app_settings: dict[str, Any] | None) -> None:
        """Reset the app and optionally replace settings used by later reconnects."""
        self._require_started()
        if app_settings is not None:
            self.settings = replace(self.settings, app_settings=app_settings)
        self.app_link.request(
            {"command": "reset", "settings": self.settings.app_settings},
            "reset_done",
            _COMMAND_TIMEOUT,
        )

    def gesture(self, request: GestureRequest) -> None:
        """Send one gesture to the app and wait for it to settle."""
        self._require_started()
        if self._system_window_in_front():
            assert self._system_window is not None
            self._system_window.gesture(request)
            return
        self.app_link.request(build_gesture_payload(request), "gestured", _COMMAND_TIMEOUT)

    def send_input(self, request: InputRequest) -> DemoEvent:
        """Send one text or key command to the app and return its typed reply."""
        self._require_started()
        if self._system_window_in_front():
            if request.kind is InputKind.TAP_TEXT:
                assert self._system_window is not None
                return self._system_window.tap_text(request)
            raise LiveError("input is not available while a system window is in front")
        return self.app_link.request(
            build_input_payload(request), request.kind.reply_event, _COMMAND_TIMEOUT
        )

    def shot(self, request: ShotRequest) -> Path:
        """Capture a named screen or the current app state and save its PNG."""
        self._require_started()
        if (
            request.orientation is not None
            and self.settings.target is not LiveTarget.ANDROID_EMULATOR
        ):
            raise LiveError("orientation requires the android_emulator target")

        try:
            rotation = nullcontext()
            if request.orientation is not None:
                assert self.emulator is not None
                rotation = self.emulator.rotation().locked(
                    request.orientation is ShotOrientation.LANDSCAPE,
                    _COMMAND_TIMEOUT,
                )
            with rotation:
                if self._system_window_in_front():
                    assert self._system_window is not None
                    return self._system_window.shot(request)
                return capture_shot(self.app_link, request, _COMMAND_TIMEOUT)
        except (LiveConnectionLost, LiveFlutterExited) as error:
            if request.screen is None or self.settings.target is not LiveTarget.ANDROID_EMULATOR:
                raise
            return recover_named_android_shot(self, request, error, _COMMAND_TIMEOUT)
        except TimeoutError as error:
            raise LiveError(str(error)) from error

    def stop(self) -> None:
        """Close the connection and stop only processes owned by this session."""
        try:
            self.daemon.stop()
        finally:
            try:
                if self.emulator is not None:
                    self.emulator.stop()
            finally:
                self.server.close()
                self._started = False
                self._system_window = None

    def _track_app_package(self) -> None:
        """Remember the connected app package for later foreground checks."""
        self._system_window = track_app_package(self.settings, self.emulator)

    def _system_window_in_front(self) -> bool:
        """Check whether a non-app Android activity currently owns the display."""
        return self._system_window is not None and self._system_window.in_front()

    def _require_started(self) -> None:
        if not self._started:
            raise LiveError("live session is not started")

    def _relaunch(self, previous_output: str) -> ReloadResult:
        return relaunch_session(self, previous_output)
