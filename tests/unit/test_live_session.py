"""Tests for live-session screenshot orchestration."""

from unittest.mock import MagicMock

import pytest

from screenshot_tool.daemon_protocol import DaemonResult
from screenshot_tool.live_config import LiveTarget
from screenshot_tool.live_session import LiveError, ShotOrientation, ShotRequest
from screenshot_tool.live_system_window import SystemWindow
from tests.unit.live_session_helpers import make_session


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


def test_stop_clears_system_window_state(tmp_path):
    session, _emulator = make_session(tmp_path)
    session._system_window = MagicMock(spec=SystemWindow)

    session.stop()

    assert session._system_window is None
