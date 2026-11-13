"""Current-state shots and gesture forwarding against the fake connector."""

from pathlib import Path

import pytest

from screenshot_tool.live_gesture import parse_gesture_request
from screenshot_tool.live_session import LiveError, LiveSession, ShotRequest


def test_gestures_accumulate_until_a_named_shot_navigates(
    live_session: LiveSession, tmp_path: Path
):
    live_session.start()
    live_session.shot(ShotRequest("todo_detail", tmp_path / "detail.png", record_id=11551))

    live_session.gesture(parse_gesture_request({"kind": "tap", "at": [0.5, 0.5]}))
    tap = tmp_path / "tap.png"
    live_session.shot(ShotRequest(None, tap))
    assert b"gestures=tap" in tap.read_bytes()

    live_session.gesture(parse_gesture_request({"kind": "pinch", "center": [0.5, 0.5], "scale": 2}))
    pinch = tmp_path / "pinch.png"
    live_session.shot(ShotRequest(None, pinch))
    assert b"gestures=tap,pinch" in pinch.read_bytes()

    live_session.gesture(
        parse_gesture_request({"kind": "drag", "from": [0.2, 0.5], "to": [0.8, 0.5]})
    )
    drag = tmp_path / "drag.png"
    live_session.shot(ShotRequest(None, drag))
    assert b"gestures=tap,pinch,drag" in drag.read_bytes()

    reset = tmp_path / "reset.png"
    live_session.shot(ShotRequest("home", reset))
    assert b"gestures=" not in reset.read_bytes()


def test_unknown_gesture_section_keeps_session_available(live_session: LiveSession, tmp_path: Path):
    live_session.start()
    with pytest.raises(LiveError, match="unknown section nope for image_viewer"):
        live_session.gesture(
            parse_gesture_request(
                {"kind": "tap", "at": [0, 0], "screen": "image_viewer", "section": "nope"}
            )
        )
    live_session.gesture(parse_gesture_request({"kind": "tap", "at": [0, 0]}))
    live_session.shot(ShotRequest(None, tmp_path / "after-error.png"))
