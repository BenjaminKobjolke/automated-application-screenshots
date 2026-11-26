"""Tests for live-session screenshot orchestration."""

from pathlib import Path
from unittest.mock import MagicMock

import pytest

from screenshot_tool.android_emulator import AndroidEmulator
from screenshot_tool.app_logger import AppLogger
from screenshot_tool.daemon_protocol import DaemonResult
from screenshot_tool.demo_protocol import DemoEvent
from screenshot_tool.demo_server import DemoServer
from screenshot_tool.device_screen import DeviceScreen
from screenshot_tool.flutter_daemon import FlutterDaemon
from screenshot_tool.live_app_link import LiveAppLink
from screenshot_tool.live_config import LiveSettings, LiveTarget
from screenshot_tool.live_gesture import GestureKind, GestureRequest
from screenshot_tool.live_input import InputKind, InputRequest
from screenshot_tool.live_session import LiveError, LiveSession, ShotOrientation, ShotRequest
from screenshot_tool.live_system_window import SystemWindow


def make_session(tmp_path: Path, target: LiveTarget = LiveTarget.ANDROID_EMULATOR):
    server = MagicMock(spec=DemoServer)
    daemon = MagicMock(spec=FlutterDaemon)
    emulator = MagicMock(spec=AndroidEmulator)
    settings = LiveSettings(target=target, port=8766, project_dir=tmp_path)
    session = LiveSession(settings, server=server, daemon=daemon, emulator=emulator)
    session.app_link = MagicMock(spec=LiveAppLink)
    session.app_link.request.return_value.png = b"fake-png"
    session._started = True
    return session, emulator


def test_shot_locks_landscape_orientation_around_capture(tmp_path):
    session, emulator = make_session(tmp_path)
    request = ShotRequest("home", tmp_path / "home.png", orientation=ShotOrientation.LANDSCAPE)

    assert session.shot(request) == tmp_path / "home.png"

    emulator.rotation.return_value.locked.assert_called_once_with(True, 60.0)
    emulator.rotation.return_value.locked.return_value.__enter__.assert_called_once()
    assert (tmp_path / "home.png").read_bytes() == b"fake-png"


def test_shot_without_orientation_does_not_request_rotation(tmp_path):
    session, emulator = make_session(tmp_path)

    session.shot(ShotRequest("home", tmp_path / "home.png"))

    emulator.rotation.assert_not_called()


def test_orientation_is_rejected_for_windows_target(tmp_path):
    session, _emulator = make_session(tmp_path, LiveTarget.WINDOWS)

    with pytest.raises(LiveError, match="orientation requires the android_emulator target"):
        session.shot(
            ShotRequest("home", tmp_path / "home.png", orientation=ShotOrientation.PORTRAIT)
        )

    session.app_link.request.assert_not_called()


def test_rotation_timeout_becomes_live_error(tmp_path):
    session, emulator = make_session(tmp_path)
    emulator.rotation.return_value.locked.side_effect = TimeoutError(
        "Android emulator emulator-5554 did not rotate to landscape before timeout"
    )

    with pytest.raises(LiveError, match="did not rotate to landscape"):
        session.shot(
            ShotRequest("home", tmp_path / "home.png", orientation=ShotOrientation.LANDSCAPE)
        )


def test_reset_without_new_settings_uses_current_settings(tmp_path):
    session, _emulator = make_session(tmp_path)

    session.reset(None)

    session.app_link.request.assert_called_once_with(
        {"command": "reset", "settings": {}}, "reset_done", 60.0
    )


def test_reset_updates_settings_used_after_hot_restart(tmp_path):
    session, _emulator = make_session(tmp_path)
    new_settings = {"demo_account_token": "recipient"}
    session.daemon.restart.side_effect = [
        DaemonResult(success=False, message="Hot reload refused"),
        DaemonResult(success=True, message="Hot restart ok"),
    ]

    session.reset(new_settings)
    result = session.reload()

    assert session.settings.app_settings == new_settings
    assert result.outcome.value == "restarted"
    session.app_link.accept_and_reset.assert_called_once_with(session.settings, 60.0)
    assert session.app_link.request.call_args.args[0] == {
        "command": "reset",
        "settings": new_settings,
    }


def test_reset_before_start_raises_live_error(tmp_path):
    session, _emulator = make_session(tmp_path)
    session._started = False

    with pytest.raises(LiveError, match="not started"):
        session.reset(None)


def test_start_wraps_unexpected_error_with_context(tmp_path):
    session, _emulator = make_session(tmp_path, LiveTarget.WINDOWS)
    session._started = False
    session.daemon.start.side_effect = OSError("boom")

    with pytest.raises(LiveError) as error:
        session.start()

    assert str(error.value).startswith("live start failed:")
    assert "boom" in str(error.value)


def test_system_window_gesture_skips_app_connector(tmp_path):
    session, _emulator = make_session(tmp_path)
    window = MagicMock(spec=SystemWindow)
    window.in_front.return_value = True
    session._system_window = window
    request = GestureRequest(GestureKind.TAP, at=(0.25, 0.24))

    session.gesture(request)

    window.gesture.assert_called_once_with(request)
    session.app_link.request.assert_not_called()


def test_system_window_tap_text_skips_app_connector(tmp_path):
    session, _emulator = make_session(tmp_path)
    window = MagicMock(spec=SystemWindow)
    window.in_front.return_value = True
    event = DemoEvent(event="text_tapped", demo=None, name=None, hwnd=None)
    window.tap_text.return_value = event
    session._system_window = window
    request = InputRequest(InputKind.TAP_TEXT, text="Allow")

    assert session.send_input(request) == event

    window.tap_text.assert_called_once_with(request)
    session.app_link.request.assert_not_called()


def test_other_system_window_input_is_rejected_without_app_request(tmp_path):
    session, _emulator = make_session(tmp_path)
    window = MagicMock(spec=SystemWindow)
    window.in_front.return_value = True
    session._system_window = window

    with pytest.raises(LiveError, match="while a system window is in front"):
        session.send_input(InputRequest(InputKind.READ_TEXT))

    session.app_link.request.assert_not_called()


def test_system_window_shot_saves_device_png_without_app_request(tmp_path):
    session, emulator = make_session(tmp_path)
    window = MagicMock(spec=SystemWindow)
    window.in_front.return_value = True
    window.shot.return_value = tmp_path / "device.png"
    session._system_window = window
    request = ShotRequest(None, tmp_path / "device.png", orientation=ShotOrientation.LANDSCAPE)

    assert session.shot(request) == tmp_path / "device.png"

    window.shot.assert_called_once_with(request)
    session.app_link.request.assert_not_called()
    emulator.rotation.return_value.locked.assert_called_once_with(True, 60.0)
    emulator.rotation.return_value.locked.return_value.__enter__.assert_called_once()


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

    assert calls.mock_calls.index(
        ("reverse_port", (8766,), {})
    ) < calls.mock_calls.index(("daemon_start", ("emulator-5554",), {}))


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

    assert calls.mock_calls.index(
        ("reverse_port", (8766,), {})
    ) < calls.mock_calls.index(("daemon_start", ("emulator-5554",), {}))


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


def test_stop_clears_system_window_state(tmp_path):
    session, _emulator = make_session(tmp_path)
    session._system_window = MagicMock(spec=SystemWindow)

    session.stop()

    assert session._system_window is None
