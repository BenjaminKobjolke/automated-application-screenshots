"""Tests for resetting app settings through live commands."""

import json
from unittest.mock import MagicMock

import pytest
from live_cli_helpers import make_cli, responses

from screenshot_tool.live_session import LiveError, LiveSession


def test_reset_forwards_app_settings_and_echoes_id():
    session = MagicMock(spec=LiveSession)
    session.start.return_value = "windows"
    cli, output = make_cli(
        [
            '{"command":"start"}',
            '{"command":"reset","app_settings":{"demo_account_token":"recipient"},"id":7}',
        ],
        session,
    )

    cli.run()

    assert responses(output)[1] == {"ok": True, "command": "reset", "id": 7}
    session.reset.assert_called_once_with({"demo_account_token": "recipient"})


def test_reset_without_app_settings_forwards_none():
    session = MagicMock(spec=LiveSession)
    session.start.return_value = "windows"
    cli, _output = make_cli(['{"command":"start"}', '{"command":"reset"}'], session)

    cli.run()

    session.reset.assert_called_once_with(None)


@pytest.mark.parametrize("value", [["recipient"], "recipient", None])
def test_reset_rejects_non_object_app_settings(value):
    session = MagicMock(spec=LiveSession)
    session.start.return_value = "windows"
    cli, output = make_cli(
        ['{"command":"start"}', json.dumps({"command": "reset", "app_settings": value})],
        session,
    )

    cli.run()

    assert responses(output)[1]["ok"] is False
    assert responses(output)[1]["error"] == "app_settings must be an object"
    session.reset.assert_not_called()


def test_reset_before_start_returns_not_started():
    session = MagicMock(spec=LiveSession)
    session.start.return_value = "windows"
    cli, output = make_cli(['{"command":"reset"}'], session)

    cli.run()

    assert responses(output)[0] == {
        "ok": False,
        "error": "not started",
        "command": "reset",
    }
    session.reset.assert_not_called()


def test_reset_live_error_becomes_failure_reply():
    session = MagicMock(spec=LiveSession)
    session.start.return_value = "windows"
    session.reset.side_effect = LiveError("app reset failed")
    cli, output = make_cli(['{"command":"start"}', '{"command":"reset"}'], session)

    cli.run()

    assert responses(output)[1] == {
        "ok": False,
        "error": "app reset failed",
        "command": "reset",
    }
