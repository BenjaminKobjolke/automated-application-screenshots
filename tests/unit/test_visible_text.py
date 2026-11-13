"""Tests for typed visible-text entries and live protocol events."""

import json

import pytest

from screenshot_tool.demo_protocol import KNOWN_EVENTS, parse_event_line
from screenshot_tool.visible_text import (
    VisibleTextEntry,
    VisibleTextKind,
    parse_visible_text,
)


def test_parse_visible_text_returns_typed_entries():
    entries = parse_visible_text(
        [
            {
                "text": "Sign in",
                "kind": "button",
                "enabled": True,
                "bounds": [0.1, 0.2, 0.8, 0.4],
            }
        ]
    )

    assert entries == (
        VisibleTextEntry("Sign in", VisibleTextKind.BUTTON, True, (0.1, 0.2, 0.8, 0.4)),
    )


def test_parse_visible_text_skips_unknown_kinds():
    entries = parse_visible_text(
        [
            {
                "text": "Known",
                "kind": "text",
                "enabled": True,
                "bounds": [0, 0, 1, 1],
            },
            {
                "text": "Future control",
                "kind": "slider",
                "enabled": True,
                "bounds": [0, 0, 1, 1],
            },
        ]
    )

    assert len(entries) == 1
    assert entries[0].text == "Known"


@pytest.mark.parametrize(
    "bounds",
    [None, "0,0,1,1", [0, 0, 1], [0, 0, 1, 1, 1], [0, 0, 1, "1"], [0, 0, -0.1, 1]],
)
def test_parse_visible_text_rejects_malformed_bounds(bounds):
    with pytest.raises(ValueError, match="bounds"):
        parse_visible_text(
            [{"text": "Hello", "kind": "text", "enabled": True, "bounds": bounds}]
        )


@pytest.mark.parametrize("enabled", ["true", 1, None])
def test_parse_visible_text_rejects_non_boolean_enabled(enabled):
    with pytest.raises(ValueError, match="enabled"):
        parse_visible_text(
            [{"text": "Hello", "kind": "text", "enabled": enabled, "bounds": [0, 0, 1, 1]}]
        )


@pytest.mark.parametrize("value", [None, {}, "not a list"])
def test_parse_visible_text_rejects_non_list_values(value):
    with pytest.raises(ValueError, match="list"):
        parse_visible_text(value)


def test_visible_text_json_omits_absent_optional_fields():
    entry = VisibleTextEntry("Email", VisibleTextKind.TEXT_FIELD, True, (0, 0, 1, 1))

    assert entry.to_json() == {
        "text": "Email",
        "kind": "text_field",
        "enabled": True,
        "bounds": [0, 0, 1, 1],
    }


def test_parse_visible_text_preserves_optional_field_values():
    entries = parse_visible_text(
        [
            {
                "text": "Current email",
                "kind": "text_field",
                "enabled": False,
                "bounds": [0.1, 0.2, 0.9, 0.3],
                "label": "Email address",
                "hint": "name@example.com",
                "value": "person@example.com",
            }
        ]
    )

    assert entries[0].to_json() == {
        "text": "Current email",
        "kind": "text_field",
        "enabled": False,
        "bounds": [0.1, 0.2, 0.9, 0.3],
        "label": "Email address",
        "hint": "name@example.com",
        "value": "person@example.com",
    }


@pytest.mark.parametrize("field", ["label", "hint", "value"])
def test_parse_visible_text_rejects_non_string_optional_fields(field):
    entry = {
        "text": "Email",
        "kind": "text_field",
        "enabled": True,
        "bounds": [0, 0, 1, 1],
        field: 1,
    }

    with pytest.raises(ValueError, match=field):
        parse_visible_text([entry])


def test_parse_visible_text_event_contains_typed_entries():
    event = parse_event_line(
        json.dumps(
            {
                "event": "visible_text",
                "entries": [
                    {
                        "text": "Sign in",
                        "kind": "button",
                        "enabled": True,
                        "bounds": [0.1, 0.2, 0.8, 0.4],
                    }
                ],
            }
        )
    )

    assert event.event == "visible_text"
    assert event.entries == (
        VisibleTextEntry("Sign in", VisibleTextKind.BUTTON, True, (0.1, 0.2, 0.8, 0.4)),
    )


@pytest.mark.parametrize(
    ("event_name", "expected"),
    [
        ("text_tapped", "text_tapped"),
        ("key_tapped", "key_tapped"),
        ("text_typed", "text_typed"),
        ("key_pressed", "key_pressed"),
    ],
)
def test_parse_input_reply_events(event_name, expected):
    assert event_name in KNOWN_EVENTS
    event = parse_event_line(json.dumps({"event": event_name}))
    assert event.event == expected


def test_parse_visible_text_event_rejects_malformed_entries():
    with pytest.raises(ValueError, match="list"):
        parse_event_line('{"event":"visible_text","entries":{}}')
