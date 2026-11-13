"""Validation and connector payloads for live input commands."""

import pytest

from screenshot_tool.live_input import (
    InputKind,
    InputRequest,
    PressKey,
    TextMatch,
    build_input_payload,
    parse_input_request,
)


@pytest.mark.parametrize(
    ("kind", "data", "payload"),
    [
        (
            InputKind.READ_TEXT,
            {},
            {"command": "read_text"},
        ),
        (
            InputKind.TAP_TEXT,
            {"text": "Sign in"},
            {"command": "tap_text", "text": "Sign in"},
        ),
        (
            InputKind.TAP_TEXT,
            {"text": "Sign", "match": "contains", "index": 1},
            {
                "command": "tap_text",
                "text": "Sign",
                "match": "contains",
                "index": 1,
            },
        ),
        (
            InputKind.TAP_KEY,
            {"key": "login_button"},
            {"command": "tap_key", "key": "login_button"},
        ),
        (
            InputKind.TYPE_TEXT,
            {"text": "person@example.test"},
            {"command": "type_text", "text": "person@example.test"},
        ),
        (
            InputKind.TYPE_TEXT,
            {"text": "hello", "field": "Email"},
            {"command": "type_text", "text": "hello", "field": "Email"},
        ),
        (
            InputKind.PRESS_KEY,
            {"key": "shift_tab"},
            {"command": "press_key", "key": "shift_tab"},
        ),
    ],
)
def test_parse_input_request_and_build_connector_payload(kind, data, payload):
    request = parse_input_request(kind, data)

    assert isinstance(request, InputRequest)
    assert request.kind is kind
    assert build_input_payload(request) == payload


def test_input_request_defaults_are_not_sent():
    request = parse_input_request(InputKind.TAP_TEXT, {"text": "Continue"})

    assert request.match is None
    assert request.index is None
    assert request.field is None
    assert build_input_payload(request) == {"command": "tap_text", "text": "Continue"}


@pytest.mark.parametrize(
    ("kind", "data", "message"),
    [
        (InputKind.TAP_TEXT, {}, "text"),
        (InputKind.TAP_TEXT, {"text": ""}, "text"),
        (InputKind.TAP_TEXT, {"text": "x", "match": "prefix"}, "match"),
        (InputKind.TAP_TEXT, {"text": "x", "index": -1}, "index"),
        (InputKind.TAP_TEXT, {"text": "x", "index": True}, "index"),
        (InputKind.TAP_TEXT, {"text": "x", "index": 1.5}, "index"),
        (InputKind.TAP_KEY, {}, "key"),
        (InputKind.TAP_KEY, {"key": ""}, "key"),
        (InputKind.TYPE_TEXT, {}, "text"),
        (InputKind.TYPE_TEXT, {"text": ""}, "text"),
        (InputKind.TYPE_TEXT, {"text": "x", "field": ""}, "field"),
        (InputKind.READ_TEXT, {"field": ""}, "field"),
        (InputKind.TAP_KEY, {"key": "submit", "field": 1}, "field"),
        (InputKind.PRESS_KEY, {"key": "enter", "field": None}, "field"),
        (InputKind.PRESS_KEY, {}, "key"),
        (InputKind.PRESS_KEY, {"key": "unknown"}, "key"),
    ],
)
def test_invalid_input_request_is_rejected(kind, data, message):
    with pytest.raises(ValueError, match=message):
        parse_input_request(kind, data)


def test_invalid_press_key_error_lists_supported_keys():
    with pytest.raises(ValueError) as error:
        parse_input_request(InputKind.PRESS_KEY, {"key": "unknown"})

    assert all(key.value in str(error.value) for key in PressKey)


def test_input_kind_reply_event_mapping_is_exhaustive():
    assert {kind.reply_event for kind in InputKind} == {
        "visible_text",
        "text_tapped",
        "key_tapped",
        "text_typed",
        "key_pressed",
    }
    assert InputKind.READ_TEXT.reply_event == "visible_text"
    assert InputKind.TAP_TEXT.reply_event == "text_tapped"
    assert InputKind.TAP_KEY.reply_event == "key_tapped"
    assert InputKind.TYPE_TEXT.reply_event == "text_typed"
    assert InputKind.PRESS_KEY.reply_event == "key_pressed"


def test_text_match_and_press_key_values_match_the_connector_contract():
    assert {value.value for value in TextMatch} == {"exact", "contains"}
    assert {value.value for value in PressKey} == {
        "enter",
        "tab",
        "shift_tab",
        "escape",
        "backspace",
        "arrow_up",
        "arrow_down",
        "arrow_left",
        "arrow_right",
    }
