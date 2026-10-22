"""Coordinate a Flutter process and its app-side automation connection."""

from __future__ import annotations

import time
from dataclasses import dataclass
from enum import Enum
from pathlib import Path

from .android_emulator import AndroidEmulator
from .demo_server import DemoEvent, DemoServer, ScreenInfo
from .flutter_daemon import FlutterDaemon
from .live_config import LiveSettings, LiveTarget, device_id

_COMMAND_TIMEOUT = 60.0
_POLL_SECONDS = 0.1
_EXIT_GRACE_SECONDS = 0.5
_UNRESPONSIVE_MESSAGE = "Flutter app stopped responding to hot reload and hot restart"


class LiveError(RuntimeError):
    """A live-session operation failed, with relevant build output if present."""

    def __init__(self, message: str, output: str = "") -> None:
        super().__init__(message)
        self.message = message
        self.output = output


class ReloadOutcome(Enum):
    """The level of Flutter restart needed to apply the current source."""

    RELOADED = "reloaded"
    RESTARTED = "restarted"
    RELAUNCHED = "relaunched"
    COMPILE_ERROR = "compile_error"
    UNRESPONSIVE = "unresponsive"
    FAILED = "failed"


@dataclass(frozen=True)
class ReloadResult:
    """Typed outcome returned by a live reload request."""

    outcome: ReloadOutcome
    message: str = ""
    output: str = ""


class ShotTheme(str, Enum):
    """Theme requested for one live screenshot."""

    DARK = "dark"
    LIGHT = "light"


@dataclass(frozen=True)
class ShotRequest:
    """Options for capturing a named live screen."""

    screen: str
    out: str | Path
    theme: ShotTheme | None = None
    section: str | None = None
    full: bool = False
    record_id: int | None = None

    def __post_init__(self) -> None:
        if self.section is not None and self.full:
            raise ValueError("section and full cannot be combined")


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
        self.emulator = (
            emulator
            if emulator is not None
            else AndroidEmulator()
            if settings.target is LiveTarget.ANDROID_EMULATOR
            else None
        )
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
            self._accept_and_reset(float(self.settings.start_timeout))
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
                self._accept_and_reset(_COMMAND_TIMEOUT)
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
        event = self._request(
            {"command": "list_screens"},
            expected="screens",
        )
        return event.screens or ()

    def shot(self, request: ShotRequest) -> Path:
        """Navigate to a named screen and save the app-provided PNG."""
        self._require_started()
        if request.theme is not None:
            self._request(
                {"command": "set_theme", "theme": request.theme.value},
                expected="theme_set",
            )
        navigation: dict[str, object] = {"command": "navigate", "screen": request.screen}
        if request.section is not None:
            navigation["section"] = request.section
        if request.record_id is not None:
            navigation["record_id"] = request.record_id
        self._request(navigation, expected="navigated")
        screenshot: dict[str, object] = {
            "command": "screenshot",
            "name": request.screen,
            "pixel_ratio": 1.0,
        }
        if request.full:
            screenshot["full"] = True
        event = self._request(
            screenshot,
            expected="screenshot",
        )
        if event.png is None:
            raise LiveError(f"app returned no PNG for screen {request.screen!r}")
        path = Path(request.out)
        try:
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_bytes(event.png)
        except OSError as error:
            raise LiveError(f"could not write screenshot {path}: {error}") from error
        return path

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

    def _accept_and_reset(self, timeout: float) -> None:
        if not self.server.accept(timeout):
            raise LiveError("Flutter app did not connect before timeout", self.daemon.output)
        self.server.send({"command": "reset", "settings": self.settings.app_settings})
        self._await_event("reset_done", timeout)

    def _request(self, request: dict[str, object], expected: str) -> DemoEvent:
        self.server.send(request)
        return self._await_event(expected, _COMMAND_TIMEOUT)

    def _await_event(self, expected: str, timeout: float) -> DemoEvent:
        deadline = time.monotonic() + timeout
        while time.monotonic() < deadline:
            if not self.daemon.is_running():
                raise LiveError("Flutter process exited while waiting for the app", self.daemon.output)
            try:
                event = self.server.next_event(min(_POLL_SECONDS, deadline - time.monotonic()))
            except (ConnectionError, OSError) as error:
                raise LiveError(str(error), self.daemon.output) from error
            if event is None:
                continue
            if event.event == "error":
                raise LiveError(event.message or "app command failed")
            if event.event == expected:
                return event
        raise LiveError(f"timed out waiting for app event {expected!r}", self.daemon.output)

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
            self._accept_and_reset(float(self.settings.start_timeout))
        except Exception as error:
            return ReloadResult(
                ReloadOutcome.COMPILE_ERROR,
                str(error),
                self.daemon.output or previous_output,
            )
        return ReloadResult(ReloadOutcome.RELAUNCHED, "Flutter app relaunched")
