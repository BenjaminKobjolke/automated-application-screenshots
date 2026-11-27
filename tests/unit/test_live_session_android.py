"""Tests for live-session recovery and Android startup behavior."""

from unittest.mock import MagicMock

import pytest

from screenshot_tool.app_logger import AppLogger
from screenshot_tool.demo_protocol import DemoEvent
from screenshot_tool.device_screen import DeviceScreen
from screenshot_tool.live_config import LiveTarget
from screenshot_tool.live_session import LiveError, ShotRequest
from screenshot_tool.live_system_window import SystemWindow
from screenshot_tool.live_types import (
    LiveConnectionLost,
    LiveFlutterExited,
    ReloadOutcome,
    ReloadResult,
)
from tests.unit.live_session_helpers import make_session


@pytest.mark.parametrize("failure", [LiveConnectionLost("lost"), LiveFlutterExited("exited")])
def test_named_android_shot_recovers_once_after_lost_connection(tmp_path, failure):
    session, emulator = make_session(tmp_path)
    session.app_link.request.side_effect = [
        failure,
        DemoEvent(event="navigated", demo=None, name="home", hwnd=None),
        DemoEvent(event="screenshot", demo=None, name="home", hwnd=None, png=b"recovered"),
    ]
    emulator.device_state.return_value = "emulator-5554 is still listed"
    emulator.ensure.return_value = "emulator-5556"
    session._relaunch = MagicMock(return_value=ReloadResult(ReloadOutcome.RELAUNCHED))

    assert session.shot(ShotRequest("home", tmp_path / "home.png")) == tmp_path / "home.png"

    emulator.ensure.assert_called_once_with(None, False, float(session.settings.start_timeout))
    assert session._device == "emulator-5556"
    session._relaunch.assert_called_once()
    assert (tmp_path / "home.png").read_bytes() == b"recovered"


def test_named_android_shot_reports_device_state_when_recovery_fails(tmp_path):
    session, emulator = make_session(tmp_path)
    session.app_link.request.side_effect = [
        LiveConnectionLost("initial disconnect"),
        LiveConnectionLost("retry disconnect"),
    ]
    emulator.device_state.return_value = "emulator-5554 is not listed by adb"
    session._relaunch = MagicMock(return_value=ReloadResult(ReloadOutcome.RELAUNCHED))

    with pytest.raises(LiveError, match="emulator-5554 is not listed by adb"):
        session.shot(ShotRequest("home", tmp_path / "home.png"))

    assert session.app_link.request.call_count == 2


@pytest.mark.parametrize(
    ("target", "screen"),
    [(LiveTarget.ANDROID_EMULATOR, None), (LiveTarget.WINDOWS, "home")],
)
def test_shot_does_not_recover_without_named_android_screen(tmp_path, target, screen):
    session, emulator = make_session(tmp_path, target)
    session.app_link.request.side_effect = LiveConnectionLost("disconnected")

    with pytest.raises(LiveConnectionLost):
        session.shot(ShotRequest(screen, tmp_path / "shot.png"))

    emulator.ensure.assert_not_called()


def test_android_start_tracks_app_package_after_connection(tmp_path):
    session, emulator = make_session(tmp_path)
    emulator.ensure.return_value = "emulator-5554"
    device_screen = MagicMock(spec=DeviceScreen)
    device_screen.foreground_package.return_value = "com.example.app"
    emulator.device_screen.return_value = device_screen
    session._started = False
    session.daemon.wait_for_started.return_value = True

    session.start()

    emulator.device_screen.assert_called_once_with()
    device_screen.foreground_package.assert_called_once_with()
    assert isinstance(session._system_window, SystemWindow)
    assert session._system_window._app_package == "com.example.app"


def test_android_start_reverses_automation_port_before_flutter_starts(tmp_path):
    session, emulator = make_session(tmp_path)
    emulator.ensure.return_value = "emulator-5554"
    session._started = False
    session.daemon.wait_for_started.return_value = True
    calls = MagicMock()
    calls.attach_mock(emulator.reverse_port, "reverse_port")
    calls.attach_mock(session.daemon.start, "daemon_start")

    session.start()

    assert calls.mock_calls.index(("reverse_port", (8766,), {})) < calls.mock_calls.index(
        ("daemon_start", ("emulator-5554",), {})
    )


def test_windows_start_does_not_reverse_port(tmp_path):
    session, emulator = make_session(tmp_path, LiveTarget.WINDOWS)
    session._started = False
    session.daemon.wait_for_started.return_value = True

    session.start()

    emulator.reverse_port.assert_not_called()


def test_relaunch_reapplies_port_reverse(tmp_path):
    session, emulator = make_session(tmp_path)
    session._device = "emulator-5554"
    session.daemon.wait_for_started.return_value = True
    calls = MagicMock()
    calls.attach_mock(emulator.reverse_port, "reverse_port")
    calls.attach_mock(session.daemon.start, "daemon_start")

    session._relaunch("")

    assert calls.mock_calls.index(("reverse_port", (8766,), {})) < calls.mock_calls.index(
        ("daemon_start", ("emulator-5554",), {})
    )


def test_android_start_keeps_app_routing_when_package_cannot_be_read(tmp_path, monkeypatch):
    session, emulator = make_session(tmp_path)
    emulator.ensure.return_value = "emulator-5554"
    device_screen = MagicMock(spec=DeviceScreen)
    device_screen.foreground_package.side_effect = OSError("adb unavailable")
    emulator.device_screen.return_value = device_screen
    session._started = False
    session.daemon.wait_for_started.return_value = True
    warning = MagicMock()
    monkeypatch.setattr(AppLogger, "warning", warning)

    session.start()

    assert session._system_window is None
    assert warning.called
