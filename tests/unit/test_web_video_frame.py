"""Unit tests for media-fragment video frame timing."""

from unittest.mock import MagicMock

import pytest
from playwright.sync_api import Page

from screenshot_tool import web_video_frame
from screenshot_tool.web_video_frame import media_start_seconds


@pytest.mark.parametrize(
    ("fragment", "expected"),
    [
        ("t=10", 10.0),
        ("t=10.5", 10.5),
        ("t=npt:10", 10.0),
        ("t=1:30", 90.0),
        ("t=00:01:30", 90.0),
        ("t=10,20", 10.0),
        ("xywh=0,0,10,10&t=5", 5.0),
    ],
)
def test_media_start_seconds_parses_supported_start_values(fragment, expected):
    assert media_start_seconds(fragment) == expected


@pytest.mark.parametrize(
    "fragment",
    ["", "intro", "t=", "t=abc", "t=,20", "t=-1", "t=1:2:3:4"],
)
def test_media_start_seconds_returns_none_for_missing_or_invalid_values(fragment):
    assert media_start_seconds(fragment) is None


def test_target_frame_paint_wait_uses_remaining_deadline(monkeypatch):
    times = iter((100.0, 101.0, 105.0, 110.0, 120.0))
    monkeypatch.setattr(web_video_frame.time, "monotonic", lambda: next(times))
    page = MagicMock(spec=Page)

    web_video_frame.wait_for_video_frame(page, "t=10")

    paint_wait = page.wait_for_function.call_args_list[-1]
    assert paint_wait.args == (web_video_frame._PAINT_JS,)
    assert paint_wait.kwargs["timeout"] == 10000
