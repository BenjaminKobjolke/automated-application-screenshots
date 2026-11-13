"""Gesture command behavior in the JSON-lines live CLI."""

from unittest.mock import MagicMock

from live_cli_helpers import make_cli, responses

from screenshot_tool.live_session import LiveError, LiveSession


def test_gesture_calls_session_and_echoes_id():
    session = MagicMock(spec=LiveSession)
    session.start.return_value = "windows"
    cli, output = make_cli(
        ['{"command":"start"}', '{"command":"gesture","kind":"tap","at":[0.2,0.3],"id":7}'],
        session,
    )

    cli.run()

    result = responses(output)[1]
    assert result == {"ok": True, "kind": "tap", "command": "gesture", "id": 7}
    session.gesture.assert_called_once()
    assert session.gesture.call_args.args[0].kind.value == "tap"


def test_invalid_gesture_does_not_call_session():
    session = MagicMock(spec=LiveSession)
    session.start.return_value = "windows"
    cli, output = make_cli(['{"command":"start"}', '{"command":"gesture","kind":"tap"}'], session)

    cli.run()

    assert responses(output)[1]["ok"] is False
    session.gesture.assert_not_called()


def test_connector_error_is_returned_unchanged():
    session = MagicMock(spec=LiveSession)
    session.start.return_value = "windows"
    session.gesture.side_effect = LiveError("unknown section nope for image_viewer")
    cli, output = make_cli(
        ['{"command":"start"}', '{"command":"gesture","kind":"tap","at":[0,0]}'], session
    )

    cli.run()

    assert responses(output)[1]["error"] == "unknown section nope for image_viewer"


def test_gesture_before_start_is_rejected():
    session = MagicMock(spec=LiveSession)
    cli, output = make_cli(['{"command":"gesture","kind":"tap","at":[0,0]}'], session)

    cli.run()

    assert responses(output)[0]["error"] == "not started"
    session.gesture.assert_not_called()
