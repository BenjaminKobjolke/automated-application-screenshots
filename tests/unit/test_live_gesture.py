"""Validation and connector payloads for live gestures."""

import pytest

from screenshot_tool.live_gesture import (
    GestureRequest,
    build_gesture_payload,
    parse_gesture_request,
)


@pytest.mark.parametrize(
    ("data", "payload"),
    [
        (
            {"kind": "tap", "at": [0.2, 0.7]},
            {"command": "gesture", "kind": "tap", "at": [0.2, 0.7]},
        ),
        (
            {"kind": "drag", "from": [0, 0.2], "to": [1, 0.8], "duration_ms": 400},
            {
                "command": "gesture",
                "kind": "drag",
                "from": [0, 0.2],
                "to": [1, 0.8],
                "duration_ms": 400,
            },
        ),
        (
            {
                "kind": "pinch",
                "center": [0.5, 0.5],
                "scale": 2,
                "screen": "image_viewer",
                "section": "image",
            },
            {
                "command": "gesture",
                "kind": "pinch",
                "center": [0.5, 0.5],
                "scale": 2.0,
                "screen": "image_viewer",
                "section": "image",
            },
        ),
    ],
)
def test_parse_gesture_and_build_connector_payload(data, payload):
    request = parse_gesture_request(data)
    assert isinstance(request, GestureRequest)
    assert build_gesture_payload(request) == payload


@pytest.mark.parametrize(
    ("data", "message"),
    [
        ({}, "kind"),
        ({"kind": "swipe"}, "kind"),
        ({"kind": "tap"}, "at"),
        ({"kind": "drag", "from": [0, 0]}, "to"),
        ({"kind": "drag", "to": [1, 1]}, "from"),
        ({"kind": "pinch", "center": [0.5, 0.5]}, "scale"),
        ({"kind": "tap", "at": [0.5]}, "two coordinates"),
        ({"kind": "tap", "at": [True, 0]}, "numbers"),
        ({"kind": "tap", "at": ["0", 0]}, "numbers"),
        ({"kind": "tap", "at": [-0.1, 0]}, "between 0 and 1"),
        ({"kind": "tap", "at": [1.1, 0]}, "between 0 and 1"),
        ({"kind": "pinch", "center": [0, 0], "scale": 0}, "positive"),
        ({"kind": "pinch", "center": [0, 0], "scale": -1}, "positive"),
        ({"kind": "pinch", "center": [0, 0], "scale": float("inf")}, "positive"),
        ({"kind": "pinch", "center": [0, 0], "scale": 10**400}, "positive"),
        ({"kind": "pinch", "center": [0, 0], "scale": True}, "positive"),
        ({"kind": "tap", "at": [0, 0], "duration_ms": 0}, "positive integer"),
        ({"kind": "tap", "at": [0, 0], "duration_ms": -1}, "positive integer"),
        ({"kind": "tap", "at": [0, 0], "duration_ms": 1.5}, "positive integer"),
        ({"kind": "tap", "at": [0, 0], "duration_ms": True}, "positive integer"),
        ({"kind": "tap", "at": [0, 0], "section": "image"}, "requires screen"),
        ({"kind": "tap", "at": [0, 0], "screen": ""}, "screen"),
        ({"kind": "tap", "at": [0, 0], "section": ""}, "section"),
    ],
)
def test_invalid_gesture_request_is_rejected(data, message):
    with pytest.raises(ValueError, match=message):
        parse_gesture_request(data)
