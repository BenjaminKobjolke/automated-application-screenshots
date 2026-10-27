"""Integration coverage for live-session reload and daemon recovery."""

from __future__ import annotations

import json
import os
from pathlib import Path

import pytest

from screenshot_tool.live_session import LiveSession, ReloadOutcome


def test_reload_succeeds_without_reconnecting(live_session: LiveSession):
    live_session.start()

    assert live_session.reload().outcome is ReloadOutcome.RELOADED


def test_daemon_ignores_unwrapped_requests(live_session: LiveSession, monkeypatch: pytest.MonkeyPatch):
    live_session.start()
    monkeypatch.setattr(
        "screenshot_tool.flutter_daemon.encode_request",
        lambda request: json.dumps(request) + "\n",
    )

    result = live_session.daemon.restart(full=False, timeout=1)

    assert not result.success
    assert result.message == "Flutter restart timed out"
    assert result.timed_out


def test_restart_timeout_reports_unresponsive_and_stops_app(
    live_session: LiveSession, monkeypatch: pytest.MonkeyPatch
):
    live_session.start()
    Path(os.environ["FLUTTER_FAKE_CONTROL"]).write_text("hang")
    monkeypatch.setattr("screenshot_tool.live_session._COMMAND_TIMEOUT", 0.5)

    result = live_session.reload()

    assert result.outcome is ReloadOutcome.UNRESPONSIVE
    assert "stopped responding" in result.message
    assert not live_session.daemon.is_running()
    assert live_session.reload().outcome is ReloadOutcome.RELAUNCHED
    assert live_session.daemon.is_running()


def test_hot_restart_fallback_reconnects_and_resets(live_session: LiveSession):
    live_session.start()
    control = Path(os.environ["FLUTTER_FAKE_CONTROL"])
    control.write_text("refuse_reload")

    result = live_session.reload()

    assert result.outcome is ReloadOutcome.RESTARTED


def test_compile_error_includes_daemon_message(live_session: LiveSession):
    live_session.start()
    control = Path(os.environ["FLUTTER_FAKE_CONTROL"])
    control.write_text("compile")

    result = live_session.reload()

    assert result.outcome is ReloadOutcome.COMPILE_ERROR
    assert "sample.dart:7" in result.message


def test_relaunches_after_daemon_exits(live_session: LiveSession):
    live_session.start()
    control = Path(os.environ["FLUTTER_FAKE_CONTROL"])
    control.write_text("exit")

    assert live_session.reload().outcome is ReloadOutcome.RELAUNCHED


def test_stop_cleans_up_daemon_process(live_session: LiveSession):
    live_session.start()
    daemon = live_session.daemon
    assert daemon.is_running()

    live_session.stop()

    assert not daemon.is_running()
