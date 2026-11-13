"""Tests for live-session screenshot orchestration."""

from pathlib import Path
from unittest.mock import MagicMock

import pytest

from screenshot_tool.android_emulator import AndroidEmulator
from screenshot_tool.demo_server import DemoServer
from screenshot_tool.flutter_daemon import FlutterDaemon
from screenshot_tool.live_app_link import LiveAppLink
from screenshot_tool.live_config import LiveSettings, LiveTarget
from screenshot_tool.live_session import LiveError, LiveSession, ShotOrientation, ShotRequest


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
