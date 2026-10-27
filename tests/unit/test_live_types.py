"""Exact app payloads built for live screenshot requests."""

from pathlib import Path

import pytest

from screenshot_tool.live_types import (
    LiveError,
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


def test_shot_request_saves_png_and_creates_missing_folders(tmp_path: Path):
    path = tmp_path / "nested" / "screenshots" / "home.png"
    request = ShotRequest("home", path)

    result = request.save_png(b"fake-png")

    assert result == path
    assert path.read_bytes() == b"fake-png"


def test_shot_request_wraps_png_write_error(tmp_path: Path):
    path = tmp_path / "existing-directory"
    path.mkdir()
    request = ShotRequest("home", path)

    with pytest.raises(LiveError, match="could not write screenshot") as error:
        request.save_png(b"fake-png")

    assert str(path) in error.value.message
