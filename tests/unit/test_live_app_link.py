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
from screenshot_tool.live_types import (
    LiveConnectionLost,
    LiveError,
    LiveEventTimeout,
    LiveFlutterExited,
)


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


def test_accept_and_reset_skips_silent_connection(tmp_path, monkeypatch):
    import screenshot_tool.live_app_link as live_app_link

    monkeypatch.setattr(live_app_link, "_RESET_REPLY_TIMEOUT", 0.2)
    link, server, _daemon, settings = make_link(tmp_path)
    server.accept.return_value = True
    server.next_event.side_effect = lambda _timeout: (
        DemoEvent(event="reset_done", demo=None, name=None, hwnd=None)
        if server.accept.call_count >= 2
        else None
    )

    started = time.monotonic()
    link.accept_and_reset(settings, 5.0)
    elapsed = time.monotonic() - started

    assert server.accept.call_count == 2
    assert elapsed < 2.0


def test_accept_and_reset_reports_silent_connection_at_timeout(tmp_path, monkeypatch):
    import screenshot_tool.live_app_link as live_app_link

    monkeypatch.setattr(live_app_link, "_RESET_REPLY_TIMEOUT", 0.2)
    link, server, _daemon, settings = make_link(tmp_path)
    server.accept.side_effect = lambda timeout: _wait_after_first_accept(server, timeout)
    server.next_event.return_value = None

    with pytest.raises(LiveError) as error:
        link.accept_and_reset(settings, 0.6)

    assert "app connected but never answered reset" in str(error.value)
    assert "accepted at" in str(error.value)
    assert "reset sent at" in str(error.value)


def test_await_event_timeout_raises_live_event_timeout(tmp_path):
    link, server, _daemon, _settings = make_link(tmp_path)
    server.next_event.return_value = None

    with pytest.raises(
        LiveEventTimeout, match="timed out waiting for app event 'reset_done'"
    ) as error:
        link.await_event("reset_done", 0.2)

    assert isinstance(error.value, LiveError)


def test_accept_and_reset_logs_accept_and_reset_times(tmp_path, monkeypatch):
    import screenshot_tool.live_app_link as live_app_link

    messages = []
    monkeypatch.setattr(live_app_link.AppLogger, "info", messages.append)
    link, server, _daemon, settings = make_link(tmp_path)
    server.accept.return_value = True
    server.next_event.return_value = DemoEvent(event="reset_done", demo=None, name=None, hwnd=None)

    link.accept_and_reset(settings, 1.0)

    assert any(message.startswith("App connection accepted at ") for message in messages)
    assert any(message.startswith("Sent 'reset' at ") for message in messages)


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

    with pytest.raises(LiveError, match=r"^Flutter app did not connect before timeout$"):
        link.accept_and_reset(settings, 1.0)


def test_await_event_marks_connection_loss_as_live_connection_lost(tmp_path):
    link, server, _daemon, _settings = make_link(tmp_path)
    server.next_event.side_effect = ConnectionError("demo app closed the event connection")

    with pytest.raises(LiveConnectionLost, match="reset_done") as error:
        link.await_event("reset_done", 1.0)

    assert isinstance(error.value, LiveError)
    assert "demo app closed the event connection" in str(error.value)


def test_await_event_marks_flutter_exit_as_recoverable(tmp_path):
    link, _server, daemon, _settings = make_link(tmp_path)
    daemon.is_running.return_value = False

    with pytest.raises(LiveFlutterExited, match=r"Flutter process exited"):
        link.await_event("navigated", 1.0)
