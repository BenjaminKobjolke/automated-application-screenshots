"""Unit tests for the JSON-lines live command interface."""

from unittest.mock import MagicMock

import pytest
from live_cli_helpers import make_cli, responses

from screenshot_tool.demo_server import ScreenInfo
from screenshot_tool.live_session import (
    LiveError,
    LiveSession,
    ReloadOutcome,
    ReloadResult,
    ShotRequest,
)
from screenshot_tool.live_types import LiveEventTimeout


def test_dispatches_commands_and_echoes_ids():
    session = MagicMock(spec=LiveSession)
    session.start.return_value = "windows"
    session.screens.return_value = (
        ScreenInfo(name="home"),
        ScreenInfo(name="habit_edit", sections=("additional_information",)),
        ScreenInfo(name="todo_detail", record_id="todo id"),
    )
    session.reload.return_value = ReloadResult(ReloadOutcome.RELOADED, "Hot reload ok")
    session.shot.return_value = "home.png"
    cli, output = make_cli(
        [
            '{"command":"start","id":1}',
            '{"command":"screens","id":"s"}',
            '{"command":"reload","id":3}',
            '{"command":"shot","screen":"home","out":"home.png","id":4}',
            '{"command":"stop","id":5}',
        ],
        session,
    )

    cli.run()

    assert responses(output) == [
        {"ok": True, "command": "start", "id": 1, "device": "windows"},
            {"ok": True, "command": "screens", "id": "s", "screens": [
                {"name": "home"},
                {"name": "habit_edit", "sections": ["additional_information"]},
                {"name": "todo_detail", "record_id": "todo id"},
            ]},
        {"ok": True, "command": "reload", "id": 3, "result": "reloaded", "message": "Hot reload ok", "output": ""},
        {"ok": True, "command": "shot", "id": 4, "path": "home.png"},
        {"ok": True, "command": "stop", "id": 5},
    ]
    session.start.assert_called_once_with()
    session.screens.assert_called_once_with()
    session.reload.assert_called_once_with()
    session.shot.assert_called_once_with(ShotRequest("home", "home.png"))
    session.stop.assert_called_once_with()


def test_malformed_and_unknown_requests_return_errors_and_continue():
    session = MagicMock(spec=LiveSession)
    cli, output = make_cli(["not json", '{"command":"who"}', '{"command":"stop"}'], session)

    cli.run()

    result = responses(output)
    assert result[0]["ok"] is False
    assert "command" not in result[0]
    assert result[1]["ok"] is False
    assert result[1]["command"] == "who"
    assert "unknown command" in str(result[1]["error"])
    assert result[2] == {"ok": True, "command": "stop"}
    session.stop.assert_called_once_with()


def test_rejects_commands_before_start_but_allows_stop():
    session = MagicMock(spec=LiveSession)
    cli, output = make_cli(['{"command":"screens"}', '{"command":"stop"}'], session)

    cli.run()

    result = responses(output)
    assert result[0] == {"ok": False, "error": "not started", "command": "screens"}
    assert result[1] == {"ok": True, "command": "stop"}
    session.screens.assert_not_called()


def test_unresponsive_reload_returns_failure_result_and_output():
    session = MagicMock(spec=LiveSession)
    session.start.return_value = "windows"
    session.reload.return_value = ReloadResult(
        ReloadOutcome.UNRESPONSIVE, "Flutter app stopped responding", "flutter log"
    )
    cli, output = make_cli(['{"command":"start"}', '{"command":"reload"}'], session)

    cli.run()

    assert responses(output)[1] == {
        "ok": False,
        "command": "reload",
        "result": "unresponsive",
        "message": "Flutter app stopped responding",
        "output": "flutter log",
    }


def test_eof_stops_session_and_live_error_includes_output():
    session = MagicMock(spec=LiveSession)
    session.start.side_effect = LiveError("Flutter failed", "compile output")
    cli, output = make_cli(['{"command":"start","id":"build"}'], session)

    cli.run()

    assert responses(output) == [
        {"ok": False, "command": "start", "id": "build", "error": "Flutter failed", "output": "compile output"}
    ]
    session.stop.assert_called_once_with()


def test_eof_without_commands_stops_session():
    session = MagicMock(spec=LiveSession)
    cli, _output = make_cli([], session)

    cli.run()

    session.stop.assert_called_once_with()


@pytest.mark.parametrize("error", [OSError("socket closed"), RuntimeError("unexpected")])
def test_unexpected_session_errors_reply_and_keep_going(error):
    session = MagicMock(spec=LiveSession)
    session.start.return_value = "android-emulator"
    session.screens.side_effect = [error, ()]
    cli, output = make_cli(
        [
            '{"command":"start"}',
            '{"command":"screens","id":"failed"}',
            '{"command":"screens","id":"next"}',
            '{"command":"stop"}',
        ],
        session,
    )

    cli.run()

    result = responses(output)
    assert result[1]["ok"] is False
    assert result[1]["command"] == "screens"
    assert result[1]["id"] == "failed"
    assert str(error) in str(result[1]["error"])
    assert result[2] == {"ok": True, "command": "screens", "id": "next", "screens": []}


def test_stalled_app_link_returns_existing_timeout_error_without_waiting(monkeypatch):
    from screenshot_tool import live_cli

    session = MagicMock(spec=LiveSession)
    session.start.return_value = "windows"
    session.screens.side_effect = LiveEventTimeout("timed out waiting for app event 'screens'")
    clock = iter((100.0, 100.0, 200.0, 260.0))
    monkeypatch.setattr(live_cli, "_now", lambda: "10:00:00")
    monkeypatch.setattr(live_cli, "monotonic", lambda: next(clock))
    cli, output = make_cli(['{"command":"start"}', '{"command":"screens","id":8}'], session)

    cli.run()

    assert responses(output)[1] == {
        "ok": False,
        "error": "timed out waiting for app event 'screens'",
        "command": "screens",
        "id": 8,
    }


def test_command_timing_and_failed_android_device_state_are_logged(caplog):
    session = MagicMock(spec=LiveSession)
    session.start.return_value = "emulator-5554"
    session.device_state.return_value = "emulator-5554 is not listed by adb"
    session.screens.side_effect = LiveError("adb command failed: adb devices")
    cli, _output = make_cli(['{"command":"start"}', '{"command":"screens","id":9}'], session)
    caplog.set_level("INFO", logger="screenshot_tool")

    cli.run()

    assert "Received 'start'" in caplog.text
    assert "'start' succeeded in" in caplog.text
    assert "Received 'screens'" in caplog.text
    assert "'screens' failed in" in caplog.text
    assert "emulator-5554 is not listed by adb" in caplog.text
