"""Shot command request and validation tests for the JSON-lines live CLI."""

import json
from unittest.mock import MagicMock

import pytest
from live_cli_helpers import make_cli, responses

from screenshot_tool.live_session import LiveError, LiveSession, ShotRequest, ShotTheme


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
    cli, output = make_cli(
        [
            '{"command":"start"}',
            json.dumps({"command": "shot", "screen": screen, "out": "x.png", **options}),
        ],
        session,
    )

    cli.run()

    assert responses(output)[1]["ok"] is True
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
    cli, output = make_cli(
        ['{"command":"start"}', json.dumps({"command": "shot", "screen": "home", "out": "x.png", **options})],
        session,
    )

    cli.run()

    assert responses(output)[1]["error"] == message
    session.shot.assert_not_called()


def test_shot_live_error_is_returned_unchanged():
    session = MagicMock(spec=LiveSession)
    session.start.return_value = "windows"
    session.shot.side_effect = LiveError("unknown section additional_information for habit_edit")
    cli, output = make_cli(
        ['{"command":"start"}', '{"command":"shot","screen":"habit_edit","out":"x.png","section":"additional_information"}'],
        session,
    )

    cli.run()

    assert responses(output)[1]["error"] == "unknown section additional_information for habit_edit"


def test_shot_request_rejects_section_and_full_together():
    with pytest.raises(ValueError, match="section and full cannot be combined"):
        ShotRequest("home", "x.png", section="a", full=True)
