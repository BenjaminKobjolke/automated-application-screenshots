"""Workflow helpers for reloading and capturing a live Flutter session."""

from __future__ import annotations

import time
from collections.abc import Callable
from pathlib import Path
from typing import Protocol

from .android_emulator import AndroidEmulator
from .app_logger import AppLogger
from .flutter_daemon import FlutterDaemon
from .live_app_link import _POLL_SECONDS, LiveAppLink
from .live_config import LiveSettings, LiveTarget
from .live_system_window import SystemWindow
from .live_types import (
    LiveError,
    ReloadOutcome,
    ReloadResult,
    ShotRequest,
    build_navigation_payload,
    build_screenshot_payload,
)

_EXIT_GRACE_SECONDS = 0.5
_UNRESPONSIVE_MESSAGE = "Flutter app stopped responding to hot reload and hot restart"


class LiveSessionWorkflowHost(Protocol):
    """Session state and callbacks used by reload workflows."""

    settings: LiveSettings
    daemon: FlutterDaemon
    app_link: LiveAppLink
    emulator: AndroidEmulator | None
    _device: str | None

    def _track_app_package(self) -> None: ...


def reload_session(session: LiveSessionWorkflowHost, command_timeout: float) -> ReloadResult:
    """Hot reload, falling back to restart and then a new Flutter run."""
    output_before = session.daemon.output
    hot_reload = session.daemon.restart(full=False, timeout=command_timeout)
    if hot_reload.success:
        return ReloadResult(ReloadOutcome.RELOADED, hot_reload.message)

    if _wait_for_daemon_exit(session.daemon.is_running):
        return relaunch_session(session, output_before)

    hot_restart = session.daemon.restart(full=True, timeout=command_timeout)
    if hot_restart.success:
        try:
            session.app_link.accept_and_reset(session.settings, command_timeout)
        except LiveError as error:
            return ReloadResult(ReloadOutcome.FAILED, error.message, error.output)
        return ReloadResult(ReloadOutcome.RESTARTED, hot_restart.message)

    if not session.daemon.is_running():
        return relaunch_session(session, output_before)

    if hot_restart.timed_out:
        output = new_output(output_before, session.daemon.output)
        session.daemon.stop()
        return ReloadResult(ReloadOutcome.UNRESPONSIVE, _UNRESPONSIVE_MESSAGE, output)

    message = hot_restart.message or hot_reload.message or "Flutter restart failed"
    return ReloadResult(
        ReloadOutcome.COMPILE_ERROR,
        message,
        new_output(output_before, session.daemon.output),
    )


def relaunch_session(session: LiveSessionWorkflowHost, previous_output: str) -> ReloadResult:
    """Start a fresh Flutter process after its previous process exits."""
    try:
        assert session._device is not None
        prepare_device(session.settings, session.emulator)
        session.daemon.start(session._device)
        wait_for_app_start(session.daemon, session.settings)
        session.app_link.accept_and_reset(session.settings, float(session.settings.start_timeout))
        session._track_app_package()
    except Exception as error:
        return ReloadResult(
            ReloadOutcome.COMPILE_ERROR,
            str(error),
            session.daemon.output or previous_output,
        )
    return ReloadResult(ReloadOutcome.RELAUNCHED, "Flutter app relaunched")


def new_output(previous: str, current: str) -> str:
    """Return only output added since a previous Flutter command."""
    if current.startswith(previous):
        return current[len(previous) :].strip()
    return current


def _wait_for_daemon_exit(is_running: Callable[[], bool]) -> bool:
    deadline = time.monotonic() + _EXIT_GRACE_SECONDS
    while is_running() and time.monotonic() < deadline:
        time.sleep(_POLL_SECONDS)
    return not is_running()


def wait_for_app_start(daemon: FlutterDaemon, settings: LiveSettings) -> None:
    """Wait until Flutter reports that the app started."""
    if not daemon.wait_for_started(float(settings.start_timeout)):
        raise LiveError("Flutter did not report app.started before timeout", daemon.output)


def prepare_device(settings: LiveSettings, emulator: AndroidEmulator | None) -> None:
    """Apply the emulator-side port mapping required by the selected target."""
    if settings.target is LiveTarget.ANDROID_EMULATOR:
        assert emulator is not None
        emulator.reverse_port(settings.port)


def capture_shot(app_link: LiveAppLink, request: ShotRequest, command_timeout: float) -> Path:
    """Ask the connected app to navigate and save the requested screenshot."""
    if request.theme is not None:
        app_link.request(
            {"command": "set_theme", "theme": request.theme.value},
            "theme_set",
            command_timeout,
        )
    if request.screen is not None:
        app_link.request(
            build_navigation_payload(request), expected="navigated", timeout=command_timeout
        )
    event = app_link.request(
        build_screenshot_payload(request), expected="screenshot", timeout=command_timeout
    )
    if event.png is None:
        screen = repr(request.screen) if request.screen is not None else "the current state"
        raise LiveError(f"app returned no PNG for {screen}")
    return request.save_png(event.png)


def track_app_package(settings: LiveSettings, emulator: AndroidEmulator | None) -> SystemWindow | None:
    """Create system-window routing for the foreground Android app when known."""
    if settings.target is not LiveTarget.ANDROID_EMULATOR:
        return None
    assert emulator is not None
    try:
        screen = emulator.device_screen()
        app_package = screen.foreground_package()
    except Exception as error:
        AppLogger.warning(f"Could not record Android app package for system-window routing: {error}")
        return None
    if app_package is None:
        AppLogger.warning(
            "Could not record Android app package for system-window routing; "
            "keeping app-only capture behavior"
        )
        return None
    return SystemWindow(screen, app_package)
