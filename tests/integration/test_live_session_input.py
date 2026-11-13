"""Live input command round trips through the fake Flutter app."""

from __future__ import annotations

from pathlib import Path

import pytest

from screenshot_tool.live_input import InputKind, parse_input_request
from screenshot_tool.live_session import LiveError
from screenshot_tool.live_types import ShotRequest


def test_live_input_commands_round_trip_and_record_actions(live_session, tmp_path: Path):
    live_session.start()

    visible_text = live_session.send_input(parse_input_request(InputKind.READ_TEXT, {}))
    tapped_text = live_session.send_input(
        parse_input_request(InputKind.TAP_TEXT, {"text": "Open details"})
    )
    tapped_key = live_session.send_input(
        parse_input_request(InputKind.TAP_KEY, {"key": "details_button"})
    )
    typed_text = live_session.send_input(
        parse_input_request(InputKind.TYPE_TEXT, {"text": "hello", "field": "Name"})
    )
    pressed_key = live_session.send_input(
        parse_input_request(InputKind.PRESS_KEY, {"key": "shift_tab"})
    )

    assert visible_text.event == "visible_text"
    assert tapped_text.event == "text_tapped"
    assert tapped_key.event == "key_tapped"
    assert typed_text.event == "text_typed"
    assert pressed_key.event == "key_pressed"

    screenshot = live_session.shot(ShotRequest(screen=None, out=tmp_path / "current.png"))
    state = screenshot.read_bytes().decode()
    assert "read_text" in state
    assert "tap_text:Open details" in state
    assert "tap_key:details_button" in state
    assert "type_text:hello:Name" in state
    assert "press_key:shift_tab" in state


def test_read_text_returns_typed_known_entries_and_skips_unknown_kind(live_session):
    live_session.start()

    event = live_session.send_input(parse_input_request(InputKind.READ_TEXT, {}))

    assert event.entries is not None
    assert len(event.entries) == 3
    assert event.entries[0].text == "Open details"
    assert event.entries[0].kind.value == "button"
    assert event.entries[1].text == "Welcome"
    assert event.entries[1].kind.value == "text"
    assert event.entries[2].text == "Name"
    assert event.entries[2].kind.value == "text_field"
    assert event.entries[2].label == "Name"
    assert event.entries[2].value == "Ada"


def test_missing_text_error_names_candidates_and_session_remains_usable(live_session):
    live_session.start()

    with pytest.raises(LiveError, match="Open details"):
        live_session.send_input(
            parse_input_request(InputKind.TAP_TEXT, {"text": "missing"})
        )

    assert tuple(screen.name for screen in live_session.screens()) == (
        "home",
        "habit_edit",
        "todo_detail",
    )
