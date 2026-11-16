"""Tests for the live app connection and its initial reset handshake."""

import time
from pathlib import Path
from unittest.mock import MagicMock

import pytest

from screenshot_tool.demo_protocol import DemoEvent
from screenshot_tool.demo_server import DemoServer
from screenshot_tool.flutter_daemon import FlutterDaemon
from screenshot_tool.live_app_link import LiveAppLink
from screenshot_tool.live_config import LiveSettings, LiveTarget
from screenshot_tool.live_types import LiveConnectionLost, LiveError


def make_link(tmp_path: Path) -> tuple[LiveAppLink, MagicMock, MagicMock, LiveSettings]:
    server = MagicMock(spec=DemoServer)
    daemon = MagicMock(spec=FlutterDaemon)
    daemon.is_running.return_value = True
    settings = LiveSettings(target=LiveTarget.WINDOWS, port=8766, project_dir=tmp_path)
    return LiveAppLink(server, daemon), server, daemon, settings


def test_accept_and_reset_skips_connection_lost_during_send(tmp_path):
    link, server, _daemon, settings = make_link(tmp_path)
    server.accept.return_value = True
    server.send.side_effect = [ConnectionAbortedError("socket closed"), None]
    server.next_event.return_value = DemoEvent(event="reset_done", demo=None, name=None, hwnd=None)

    link.accept_and_reset(settings, 1.0)

    assert server.accept.call_count == 2
    server.send.assert_called_with({"command": "reset", "settings": {}})


def test_accept_and_reset_skips_connection_lost_while_waiting(tmp_path):
    link, server, _daemon, settings = make_link(tmp_path)
    server.accept.return_value = True
    server.next_event.side_effect = [
        ConnectionError("demo app closed the event connection"),
        DemoEvent(event="reset_done", demo=None, name=None, hwnd=None),
    ]

    link.accept_and_reset(settings, 1.0)

    assert server.accept.call_count == 2


def test_accept_and_reset_reports_last_connection_error_at_timeout(tmp_path):
    link, server, _daemon, settings = make_link(tmp_path)
    server.accept.side_effect = lambda timeout: _wait_after_first_accept(server, timeout)
    server.next_event.side_effect = ConnectionError("demo app closed the event connection")

    with pytest.raises(LiveError) as error:
        link.accept_and_reset(settings, 0.3)

    assert "app connection lost before 'reset_done'" in str(error.value)
    assert "demo app closed the event connection" in str(error.value)


def _wait_after_first_accept(server: MagicMock, timeout: float) -> bool:
    if server.accept.call_count == 1:
        return True
    time.sleep(timeout)
    return False


def test_accept_timeout_without_connection_loss_keeps_existing_message(tmp_path):
    link, server, _daemon, settings = make_link(tmp_path)
    server.accept.return_value = False

    with pytest.raises(LiveError, match="^Flutter app did not connect before timeout$"):
        link.accept_and_reset(settings, 1.0)


def test_await_event_marks_connection_loss_as_live_connection_lost(tmp_path):
    link, server, _daemon, _settings = make_link(tmp_path)
    server.next_event.side_effect = ConnectionError("demo app closed the event connection")

    with pytest.raises(LiveConnectionLost, match="reset_done") as error:
        link.await_event("reset_done", 1.0)

    assert isinstance(error.value, LiveError)
    assert "demo app closed the event connection" in str(error.value)
