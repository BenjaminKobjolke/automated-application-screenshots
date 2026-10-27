"""Exact app payloads built for live screenshot requests."""

import pytest

from screenshot_tool.live_types import (
    ShotRequest,
    build_navigation_payload,
    build_screenshot_payload,
)


@pytest.mark.parametrize(
    ("shot_request", "navigation", "screenshot"),
    [
        (
            ShotRequest("home", "home.png"),
            {"command": "navigate", "screen": "home"},
            {"command": "screenshot", "name": "home", "pixel_ratio": 1.0},
        ),
        (
            ShotRequest("habit_edit", "habit.png", section="additional_information"),
            {
                "command": "navigate",
                "screen": "habit_edit",
                "section": "additional_information",
            },
            {"command": "screenshot", "name": "habit_edit", "pixel_ratio": 1.0},
        ),
        (
            ShotRequest("todo_detail", "todo.png", record_id=11551),
            {"command": "navigate", "screen": "todo_detail", "record_id": 11551},
            {"command": "screenshot", "name": "todo_detail", "pixel_ratio": 1.0},
        ),
        (
            ShotRequest("home", "home-de.png", language="de"),
            {"command": "navigate", "screen": "home", "language": "de"},
            {"command": "screenshot", "name": "home", "pixel_ratio": 1.0},
        ),
        (
            ShotRequest("home", "home-full.png", full=True),
            {"command": "navigate", "screen": "home"},
            {"command": "screenshot", "name": "home", "pixel_ratio": 1.0, "full": True},
        ),
    ],
)
def test_builds_exact_navigation_and_screenshot_payloads(shot_request, navigation, screenshot):
    assert build_navigation_payload(shot_request) == navigation
    assert build_screenshot_payload(shot_request) == screenshot
