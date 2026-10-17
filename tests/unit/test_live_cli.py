"""Unit tests for the JSON-lines live command interface."""

import io
import json
from unittest.mock import MagicMock

import pytest

from screenshot_tool.live_cli import LiveCLI
from screenshot_tool.live_session import LiveError, ReloadOutcome, ReloadResult, LiveSession
from screenshot_tool.demo_server import ScreenInfo


def _cli(lines: list[str], session: LiveSession) -> tuple[LiveCLI, io.StringIO]:
    output = io.StringIO()
    return LiveCLI(session, io.StringIO("\n".join(lines) + "\n"), output), output


def _responses(output: io.StringIO) -> list[dict[str, object]]:
    return [json.loads(line) for line in output.getvalue().splitlines()]


def test_dispatches_commands_and_echoes_ids():
    session = MagicMock(spec=LiveSession)
    session.start.return_value = "windows"
    session.screens.return_value = (ScreenInfo(name="home"),)
    session.reload.return_value = ReloadResult(ReloadOutcome.RELOADED, "Hot reload ok")
    session.shot.return_value = "home.png"
    cli, output = _cli(
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

    assert _responses(output) == [
        {"ok": True, "command": "start", "id": 1, "device": "windows"},
        {"ok": True, "command": "screens", "id": "s", "screens": [{"name": "home"}]},
        {"ok": True, "command": "reload", "id": 3, "result": "reloaded", "message": "Hot reload ok", "output": ""},
        {"ok": True, "command": "shot", "id": 4, "path": "home.png"},
        {"ok": True, "command": "stop", "id": 5},
    ]
    session.start.assert_called_once_with()
    session.screens.assert_called_once_with()
    session.reload.assert_called_once_with()
    session.shot.assert_called_once_with("home", "home.png")
    session.stop.assert_called_once_with()


def test_malformed_and_unknown_requests_return_errors_and_continue():
    session = MagicMock(spec=LiveSession)
    cli, output = _cli(["not json", '{"command":"who"}', '{"command":"stop"}'], session)

    cli.run()

    responses = _responses(output)
    assert responses[0]["ok"] is False
    assert "command" not in responses[0]
    assert responses[1]["ok"] is False
    assert responses[1]["command"] == "who"
    assert "unknown command" in str(responses[1]["error"])
    assert responses[2] == {"ok": True, "command": "stop"}
    session.stop.assert_called_once_with()


def test_rejects_commands_before_start_but_allows_stop():
    session = MagicMock(spec=LiveSession)
    cli, output = _cli(['{"command":"screens"}', '{"command":"stop"}'], session)

    cli.run()

    responses = _responses(output)
    assert responses[0] == {"ok": False, "error": "not started", "command": "screens"}
    assert responses[1] == {"ok": True, "command": "stop"}
    session.screens.assert_not_called()


def test_eof_stops_session_and_live_error_includes_output():
    session = MagicMock(spec=LiveSession)
    session.start.side_effect = LiveError("Flutter failed", "compile output")
    cli, output = _cli(['{"command":"start","id":"build"}'], session)

    cli.run()

    assert _responses(output) == [
        {"ok": False, "command": "start", "id": "build", "error": "Flutter failed", "output": "compile output"}
    ]
    session.stop.assert_called_once_with()


def test_eof_without_commands_stops_session():
    session = MagicMock(spec=LiveSession)
    cli = LiveCLI(session, io.StringIO(""), io.StringIO())

    cli.run()

    session.stop.assert_called_once_with()
