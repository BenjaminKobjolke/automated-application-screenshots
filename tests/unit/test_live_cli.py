"""Unit tests for the JSON-lines live command interface."""

import io
import json
from unittest.mock import MagicMock

import pytest

from screenshot_tool.demo_server import ScreenInfo
from screenshot_tool.live_cli import LiveCLI
from screenshot_tool.live_session import (
    LiveError,
    LiveSession,
    ReloadOutcome,
    ReloadResult,
    ShotRequest,
    ShotTheme,
)


def _cli(lines: list[str], session: LiveSession) -> tuple[LiveCLI, io.StringIO]:
    output = io.StringIO()
    return LiveCLI(session, io.StringIO("\n".join(lines) + "\n"), output), output


def _responses(output: io.StringIO) -> list[dict[str, object]]:
    return [json.loads(line) for line in output.getvalue().splitlines()]


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


def test_unresponsive_reload_returns_failure_result_and_output():
    session = MagicMock(spec=LiveSession)
    session.start.return_value = "windows"
    session.reload.return_value = ReloadResult(
        ReloadOutcome.UNRESPONSIVE, "Flutter app stopped responding", "flutter log"
    )
    cli, output = _cli(['{"command":"start"}', '{"command":"reload"}'], session)

    cli.run()

    assert _responses(output)[1] == {
        "ok": False,
        "command": "reload",
        "result": "unresponsive",
        "message": "Flutter app stopped responding",
        "output": "flutter log",
    }


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


@pytest.mark.parametrize(
    ("options", "expected"),
    [
        ({"theme": "dark", "section": "additional_information"}, ShotRequest(
            "habit_edit", "x.png", ShotTheme.DARK, "additional_information"
        )),
        ({"full": True}, ShotRequest("home", "x.png", full=True)),
        ({"record_id": 11551}, ShotRequest("todo_detail", "x.png", record_id=11551)),
        (
            {"theme": "dark", "record_id": 7},
            ShotRequest("todo_detail", "x.png", ShotTheme.DARK, record_id=7),
        ),
        ({"language": "de"}, ShotRequest("home", "x.png", language="de")),
        (
            {"theme": "dark", "language": "pt_BR"},
            ShotRequest("home", "x.png", ShotTheme.DARK, language="pt_BR"),
        ),
    ],
)
def test_shot_options_build_typed_request(options, expected):
    session = MagicMock(spec=LiveSession)
    session.start.return_value = "windows"
    screen = "habit_edit" if "section" in options else "home"
    if "record_id" in options:
        screen = "todo_detail"
    cli, output = _cli(
        [
            '{"command":"start"}',
            json.dumps({
                "command": "shot",
                "screen": screen,
                "out": "x.png",
                **options,
            }),
        ],
        session,
    )

    cli.run()

    assert _responses(output)[1]["ok"] is True
    session.shot.assert_called_once_with(expected)


@pytest.mark.parametrize(
    ("options", "message"),
    [
        ({"theme": "blue"}, "theme must be dark or light"),
        ({"theme": None}, "theme must be dark or light"),
        ({"full": 1}, "full must be a boolean"),
        ({"section": ""}, "section must be a non-empty string"),
        ({"section": None}, "section must be a non-empty string"),
        ({"section": "a", "full": True}, "section and full cannot be combined"),
        ({"record_id": "11551"}, "record_id must be an integer"),
        ({"record_id": 1.5}, "record_id must be an integer"),
        ({"record_id": True}, "record_id must be an integer"),
        ({"record_id": None}, "record_id must be an integer"),
        ({"language": ""}, "language must be a language code such as de or en-US"),
        ({"language": None}, "language must be a language code such as de or en-US"),
        ({"language": 5}, "language must be a language code such as de or en-US"),
        ({"language": "german!"}, "language must be a language code such as de or en-US"),
        ({"language": "d"}, "language must be a language code such as de or en-US"),
    ],
)
def test_invalid_shot_options_return_errors(options, message):
    session = MagicMock(spec=LiveSession)
    session.start.return_value = "windows"
    cli, output = _cli(
        ['{"command":"start"}', json.dumps({"command": "shot", "screen": "home", "out": "x.png", **options})],
        session,
    )

    cli.run()

    assert _responses(output)[1]["error"] == message
    session.shot.assert_not_called()


def test_shot_live_error_is_returned_unchanged():
    session = MagicMock(spec=LiveSession)
    session.start.return_value = "windows"
    session.shot.side_effect = LiveError("unknown section additional_information for habit_edit")
    cli, output = _cli(
        ['{"command":"start"}', '{"command":"shot","screen":"habit_edit","out":"x.png","section":"additional_information"}'],
        session,
    )

    cli.run()

    assert _responses(output)[1]["error"] == "unknown section additional_information for habit_edit"


def test_shot_request_rejects_section_and_full_together():
    with pytest.raises(ValueError, match="section and full cannot be combined"):
        ShotRequest("home", "x.png", section="a", full=True)
