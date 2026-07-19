"""Unit tests for demo event line parsing."""

import pytest

from screenshot_tool.demo_server import DemoEvent, parse_event_line


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
