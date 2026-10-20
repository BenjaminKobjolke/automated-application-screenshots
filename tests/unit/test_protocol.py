"""Unit tests for demo event line parsing."""

import pytest

from screenshot_tool.demo_server import DemoEvent, ScreenInfo, parse_event_line


def test_parse_demo_started_with_hwnd():
    event = parse_event_line('{"event": "demo_started", "demo": 1, "hwnd": 264854}')
    assert event == DemoEvent(event="demo_started", demo=1, name=None, hwnd=264854)


def test_parse_demo_started_without_hwnd():
    event = parse_event_line('{"event": "demo_started", "demo": 1}')
    assert event == DemoEvent(event="demo_started", demo=1, name=None, hwnd=None)


def test_parse_screenshot():
    event = parse_event_line('{"event": "screenshot", "name": "basic-results"}')
    assert event == DemoEvent(event="screenshot", demo=None, name="basic-results", hwnd=None)


def test_parse_demo_ended():
    event = parse_event_line('{"event": "demo_ended", "demo": 3}')
    assert event == DemoEvent(event="demo_ended", demo=3, name=None, hwnd=None)


@pytest.mark.parametrize("line", ["not json", "[]", '{"no_event": 1}', ""])
def test_garbage_raises_value_error(line):
    with pytest.raises(ValueError):
        parse_event_line(line)


# --- network mode events ---------------------------------------------------


def test_parse_screenshot_with_inline_png_decodes_base64():
    event = parse_event_line('{"event": "screenshot", "name": "home", "png": "aGVsbG8="}')
    assert event.name == "home"
    assert event.png == b"hello"


def test_parse_video_header_carries_size():
    event = parse_event_line('{"event": "video", "demo": 1, "size": 1234}')
    assert event.event == "video" and event.demo == 1 and event.size == 1234


def test_parse_error_carries_message():
    event = parse_event_line('{"event": "error", "message": "unknown demo 7"}')
    assert event.event == "error" and event.message == "unknown demo 7"


def test_parse_live_screens_event():
    event = parse_event_line(
        '{"event":"screens","screens":[{"name":"home","description":"Home",'
        '"needs_login":false}]}'
    )
    assert event.screens == (ScreenInfo(name="home", description="Home", needs_login=False),)


def test_parse_live_screens_sections():
    event = parse_event_line(
        '{"event":"screens","screens":[{"name":"habit_edit",'
        '"sections":["additional_information"]}]}'
    )
    assert event.screens == (ScreenInfo(name="habit_edit", sections=("additional_information",)),)


def test_parse_live_screens_sections_default_to_empty():
    event = parse_event_line('{"event":"screens","screens":[{"name":"home"}]}')
    assert event.screens == (ScreenInfo(name="home"),)


@pytest.mark.parametrize("sections", ['"x"', "[1]"])
def test_parse_live_screens_rejects_invalid_sections(sections):
    with pytest.raises(ValueError, match="screen sections must be a list of strings"):
        parse_event_line(f'{{"event":"screens","screens":[{{"name":"home","sections":{sections}}}]}}')


def test_parse_theme_set_event():
    event = parse_event_line('{"event":"theme_set","theme":"dark"}')
    assert event.event == "theme_set"


def test_parse_live_screens_rejects_missing_name():
    with pytest.raises(ValueError, match="screen metadata requires a string name"):
        parse_event_line('{"event":"screens","screens":[{"description":"Home"}]}')


def test_parse_live_screens_rejects_non_list_metadata():
    with pytest.raises(ValueError, match="screens metadata must be a list"):
        parse_event_line('{"event":"screens","screens":{}}')


def test_parse_live_navigated_event():
    event = parse_event_line('{"event":"navigated","screen":"settings"}')
    assert event.screen == "settings"


def test_parse_live_reset_done_event():
    event = parse_event_line('{"event":"reset_done"}')
    assert event.event == "reset_done"
