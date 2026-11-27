"""Tests for routing live-session actions through Android system windows."""

from pathlib import Path
from unittest.mock import MagicMock

import pytest

from screenshot_tool.android_emulator import AndroidEmulator
from screenshot_tool.demo_protocol import DemoEvent
from screenshot_tool.demo_server import DemoServer
from screenshot_tool.flutter_daemon import FlutterDaemon
from screenshot_tool.live_app_link import LiveAppLink
from screenshot_tool.live_config import LiveSettings, LiveTarget
from screenshot_tool.live_gesture import GestureKind, GestureRequest
from screenshot_tool.live_input import InputKind, InputRequest
from screenshot_tool.live_session import LiveError, LiveSession, ShotOrientation, ShotRequest
from screenshot_tool.live_system_window import SystemWindow


def make_session(tmp_path: Path):
    server = MagicMock(spec=DemoServer)
    daemon = MagicMock(spec=FlutterDaemon)
    emulator = MagicMock(spec=AndroidEmulator)
    settings = LiveSettings(target=LiveTarget.ANDROID_EMULATOR, port=8766, project_dir=tmp_path)
    session = LiveSession(settings, server=server, daemon=daemon, emulator=emulator)
    session.app_link = MagicMock(spec=LiveAppLink)
    session._started = True
    return session, emulator


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
