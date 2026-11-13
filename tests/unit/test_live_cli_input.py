"""Text and key command behavior in the JSON-lines live CLI."""

import json
from unittest.mock import MagicMock

import pytest
from live_cli_helpers import make_cli, responses

from screenshot_tool.demo_protocol import DemoEvent
from screenshot_tool.live_app_link import LiveAppLink
from screenshot_tool.live_cli import LiveCLI, LiveReply
from screenshot_tool.live_config import LiveSettings, LiveTarget
from screenshot_tool.live_input import InputKind, parse_input_request
from screenshot_tool.live_session import LiveError, LiveSession
from screenshot_tool.visible_text import VisibleTextEntry, VisibleTextKind


@pytest.mark.parametrize(
    ("command_request", "reply", "payload"),
    [
        (
            {"command": "read_text", "id": "read"},
            {"ok": True, "entries": [{"text": "Sign in", "kind": "button", "enabled": True,
                                        "bounds": [0.1, 0.2, 0.8, 0.3]}]},
            {"kind": InputKind.READ_TEXT},
        ),
        (
            {"command": "tap_text", "text": "Sign in", "match": "contains", "index": 1,
             "id": 2},
            {"ok": True, "text": "Sign in"},
            {"kind": InputKind.TAP_TEXT, "text": "Sign in", "match": "contains", "index": 1},
        ),
        (
            {"command": "tap_key", "key": "login_button"},
            {"ok": True, "key": "login_button"},
            {"kind": InputKind.TAP_KEY, "key": "login_button"},
        ),
        (
            {"command": "type_text", "text": "me@example.test", "field": "Email"},
            {"ok": True, "text": "me@example.test"},
            {"kind": InputKind.TYPE_TEXT, "text": "me@example.test", "field": "Email"},
        ),
        (
            {"command": "press_key", "key": "shift_tab"},
            {"ok": True, "key": "shift_tab"},
            {"kind": InputKind.PRESS_KEY, "key": "shift_tab"},
        ),
    ],
)
def test_input_commands_send_typed_request_and_echo_response(command_request, reply, payload):
    session = MagicMock(spec=LiveSession)
    session.start.return_value = "windows"
    if command_request["command"] == "read_text":
        entry = VisibleTextEntry(
            text="Sign in", kind=VisibleTextKind.BUTTON, enabled=True,
            bounds=(0.1, 0.2, 0.8, 0.3),
        )
        session.send_input.return_value = DemoEvent(
            event="visible_text", demo=None, name=None, hwnd=None, entries=(entry,)
        )
    cli, output = make_cli(
        [json.dumps({"command": "start"}), json.dumps(command_request)], session
    )

    cli.run()

    result = responses(output)[1]
    assert {key: value for key, value in result.items() if key not in {"command", "id"}} == reply
    assert result["command"] == command_request["command"]
    if "id" in command_request:
        assert result["id"] == command_request["id"]
    sent = session.send_input.call_args.args[0]
    assert sent.kind is payload["kind"]
    for field in ("text", "match", "index", "key", "field"):
        expected = payload.get(field)
        actual = getattr(sent, field)
        assert getattr(actual, "value", actual) == expected


def test_invalid_input_returns_error_with_command_and_id():
    session = MagicMock(spec=LiveSession)
    session.start.return_value = "windows"
    cli, output = make_cli(
        ['{"command":"start"}', '{"command":"tap_text","text":"","id":9}'], session
    )

    cli.run()

    assert responses(output)[1] == {
        "ok": False,
        "error": "text must be a non-empty string",
        "command": "tap_text",
        "id": 9,
    }
    session.send_input.assert_not_called()


def test_live_error_from_session_is_returned_with_command_and_id():
    session = MagicMock(spec=LiveSession)
    session.start.return_value = "windows"
    session.send_input.side_effect = LiveError("no visible text matched; candidates: Cancel")
    cli, output = make_cli(
        ['{"command":"start"}', '{"command":"tap_text","text":"Sign in","id":3}'], session
    )

    cli.run()

    assert responses(output)[1] == {
        "ok": False,
        "error": "no visible text matched; candidates: Cancel",
        "command": "tap_text",
        "id": 3,
    }


@pytest.mark.parametrize(
    "command_request",
    [
        {"command": "read_text"},
        {"command": "tap_text", "text": "Sign in"},
        {"command": "tap_key", "key": "login_button"},
        {"command": "type_text", "text": "value"},
        {"command": "press_key", "key": "enter"},
    ],
)
def test_input_commands_before_start_are_rejected(command_request):
    session = MagicMock(spec=LiveSession)
    cli, output = make_cli([json.dumps(command_request)], session)

    cli.run()

    assert responses(output)[0]["error"] == "not started"
    session.send_input.assert_not_called()


def test_respond_only_stops_loop_for_stop_command():
    session = MagicMock(spec=LiveSession)
    cli = LiveCLI(session)

    reply = cli.respond('{"command":"stop","id":5}')

    assert isinstance(reply, LiveReply)
    assert reply.response == {"ok": True, "command": "stop", "id": 5}
    assert reply.keep_going is False

    continuing = cli.respond('{"command":"screens"}')
    assert continuing.keep_going is True


def test_live_session_sends_input_payload_with_expected_reply_event():
    session = LiveSession(
        LiveSettings(target=LiveTarget.WINDOWS, port=1234),
        server=MagicMock(),
        daemon=MagicMock(),
    )
    session._started = True
    session.app_link = MagicMock(spec=LiveAppLink)
    expected_event = DemoEvent(event="text_tapped", demo=None, name=None, hwnd=None)
    session.app_link.request.return_value = expected_event
    request = parse_input_request(InputKind.TAP_TEXT, {"text": "Sign in", "match": "exact"})

    result = session.send_input(request)

    assert result is expected_event
    session.app_link.request.assert_called_once_with(
        {"command": "tap_text", "text": "Sign in", "match": "exact"},
        "text_tapped",
        60.0,
    )
