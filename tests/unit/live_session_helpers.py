"""Shared setup for live-session unit tests."""

from pathlib import Path
from unittest.mock import MagicMock

from screenshot_tool.android_emulator import AndroidEmulator
from screenshot_tool.demo_server import DemoServer
from screenshot_tool.flutter_daemon import FlutterDaemon
from screenshot_tool.live_app_link import LiveAppLink
from screenshot_tool.live_config import LiveSettings, LiveTarget
from screenshot_tool.live_session import LiveSession


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
