"""Coordinate a Flutter process and its app-side automation connection."""

from __future__ import annotations

import time
from pathlib import Path

from .android_emulator import AndroidEmulator
from .demo_server import DemoServer, ScreenInfo
from .flutter_daemon import FlutterDaemon
from .live_app_link import _POLL_SECONDS, LiveAppLink
from .live_config import LiveSettings, LiveTarget, device_id
from .live_types import (
    LiveError,
    ReloadOutcome,
    ReloadResult,
    ShotRequest,
    ShotTheme,
    build_navigation_payload,
    build_screenshot_payload,
)

_COMMAND_TIMEOUT = 60.0
_EXIT_GRACE_SECONDS = 0.5
_UNRESPONSIVE_MESSAGE = "Flutter app stopped responding to hot reload and hot restart"

__all__ = ["LiveError", "LiveSession", "ReloadOutcome", "ReloadResult", "ShotRequest", "ShotTheme"]


class LiveSession:
    """Own the app connection, Flutter process, and optional emulator lifecycle."""

    def __init__(
        self,
        settings: LiveSettings,
        server: DemoServer | None = None,
        daemon: FlutterDaemon | None = None,
        emulator: AndroidEmulator | None = None,
    ) -> None:
        self.settings = settings
        self.server = server if server is not None else DemoServer(port=settings.port)
        self.daemon = daemon if daemon is not None else FlutterDaemon(settings)
        self.app_link = LiveAppLink(self.server, self.daemon)
        if emulator is not None:
            self.emulator = emulator
        elif settings.target is LiveTarget.ANDROID_EMULATOR:
            self.emulator = AndroidEmulator()
        else:
            self.emulator = None
        self._device: str | None = None
        self._started = False

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
            self.daemon.start(self._device)
            self._wait_for_app_start()
            self.app_link.accept_and_reset(self.settings, float(self.settings.start_timeout))
            self._started = True
            return self._device
        except Exception as error:
            output = self.daemon.output
            self.stop()
            if isinstance(error, LiveError):
                raise
            raise LiveError(str(error), output) from error

    def reload(self) -> ReloadResult:
        """Hot reload, falling back to hot restart and then a new Flutter run."""
        self._require_started()
        output_before = self.daemon.output
        hot_reload = self.daemon.restart(full=False, timeout=_COMMAND_TIMEOUT)
        if hot_reload.success:
            return ReloadResult(ReloadOutcome.RELOADED, hot_reload.message)

        if self._wait_for_daemon_exit():
            return self._relaunch(output_before)

        hot_restart = self.daemon.restart(full=True, timeout=_COMMAND_TIMEOUT)
        if hot_restart.success:
            try:
                self.app_link.accept_and_reset(self.settings, _COMMAND_TIMEOUT)
            except LiveError as error:
                return ReloadResult(ReloadOutcome.FAILED, error.message, error.output)
            return ReloadResult(ReloadOutcome.RESTARTED, hot_restart.message)

        if not self.daemon.is_running():
            return self._relaunch(output_before)

        if hot_restart.timed_out:
            output = self._new_output(output_before)
            # The app froze, so the next reload needs a fresh Flutter run.
            self.daemon.stop()
            return ReloadResult(ReloadOutcome.UNRESPONSIVE, _UNRESPONSIVE_MESSAGE, output)

        message = hot_restart.message or hot_reload.message or "Flutter restart failed"
        return ReloadResult(
            ReloadOutcome.COMPILE_ERROR,
            message,
            self._new_output(output_before),
        )

    def screens(self) -> tuple[ScreenInfo, ...]:
        """Ask the app for its registered screens."""
        self._require_started()
        event = self.app_link.request({"command": "list_screens"}, "screens", _COMMAND_TIMEOUT)
        return event.screens or ()

    def shot(self, request: ShotRequest) -> Path:
        """Navigate to a named screen and save the app-provided PNG."""
        self._require_started()
        if request.theme is not None:
            self.app_link.request(
                {"command": "set_theme", "theme": request.theme.value}, "theme_set", _COMMAND_TIMEOUT
            )
        self.app_link.request(
            build_navigation_payload(request), expected="navigated", timeout=_COMMAND_TIMEOUT
        )
        event = self.app_link.request(
            build_screenshot_payload(request), expected="screenshot", timeout=_COMMAND_TIMEOUT
        )
        if event.png is None:
            raise LiveError(f"app returned no PNG for screen {request.screen!r}")
        return request.save_png(event.png)

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

    def _wait_for_app_start(self) -> None:
        if not self.daemon.wait_for_started(float(self.settings.start_timeout)):
            raise LiveError("Flutter did not report app.started before timeout", self.daemon.output)

    def _require_started(self) -> None:
        if not self._started:
            raise LiveError("live session is not started")

    def _new_output(self, previous: str) -> str:
        current = self.daemon.output
        if current.startswith(previous):
            return current[len(previous) :].strip()
        return current

    def _wait_for_daemon_exit(self) -> bool:
        deadline = time.monotonic() + _EXIT_GRACE_SECONDS
        while self.daemon.is_running() and time.monotonic() < deadline:
            time.sleep(_POLL_SECONDS)
        return not self.daemon.is_running()

    def _relaunch(self, previous_output: str) -> ReloadResult:
        try:
            assert self._device is not None
            self.daemon.start(self._device)
            self._wait_for_app_start()
            self.app_link.accept_and_reset(self.settings, float(self.settings.start_timeout))
        except Exception as error:
            return ReloadResult(
                ReloadOutcome.COMPILE_ERROR,
                str(error),
                self.daemon.output or previous_output,
            )
        return ReloadResult(ReloadOutcome.RELAUNCHED, "Flutter app relaunched")
