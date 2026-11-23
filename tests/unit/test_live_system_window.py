"""Tests for routing Android system-window work around the app connector."""

from pathlib import Path
from unittest.mock import MagicMock

import pytest

from screenshot_tool.demo_protocol import DemoEvent
from screenshot_tool.device_screen import DeviceScreen
from screenshot_tool.live_gesture import GestureKind, GestureRequest
from screenshot_tool.live_input import InputKind, InputRequest, TextMatch
from screenshot_tool.live_system_window import SystemWindow
from screenshot_tool.live_types import LiveError, ShotRequest, ShotTheme


def test_in_front_requires_a_known_app_package_and_different_foreground():
    screen = MagicMock(spec=DeviceScreen)

    assert not SystemWindow(screen, None).in_front()
    screen.foreground_package.return_value = "com.example.app"
    assert not SystemWindow(screen, "com.example.app").in_front()
    screen.foreground_package.return_value = "com.android.documentsui"
    assert SystemWindow(screen, "com.example.app").in_front()


def test_in_front_logs_and_returns_false_when_foreground_read_fails(monkeypatch):
    from screenshot_tool import live_system_window

    screen = MagicMock(spec=DeviceScreen)
    screen.foreground_package.side_effect = OSError("adb unavailable")
    warning = MagicMock()
    monkeypatch.setattr(live_system_window.AppLogger, "warning", warning)

    assert not SystemWindow(screen, "com.example.app").in_front()
    warning.assert_called_once()


def test_in_front_logs_when_foreground_package_cannot_be_parsed(monkeypatch):
    from screenshot_tool import live_system_window

    screen = MagicMock(spec=DeviceScreen)
    screen.foreground_package.return_value = None
    warning = MagicMock()
    monkeypatch.setattr(live_system_window.AppLogger, "warning", warning)

    assert not SystemWindow(screen, "com.example.app").in_front()
    warning.assert_called_once()


def test_gesture_routes_taps_and_drags_to_the_device():
    screen = MagicMock(spec=DeviceScreen)
    window = SystemWindow(screen, "com.example.app")

    window.gesture(GestureRequest(GestureKind.TAP, at=(0.25, 0.24)))
    window.gesture(
        GestureRequest(
            GestureKind.DRAG,
            from_point=(0.1, 0.2),
            to=(0.8, 0.9),
            duration_ms=450,
        )
    )

    screen.tap.assert_called_once_with(0.25, 0.24)
    screen.swipe.assert_called_once_with((0.1, 0.2), (0.8, 0.9), 450)


@pytest.mark.parametrize(
    "gesture_request",
    [
        GestureRequest(GestureKind.PINCH, center=(0.5, 0.5), scale=1.5),
        GestureRequest(GestureKind.TAP, at=(0.5, 0.5), screen="home"),
        GestureRequest(GestureKind.TAP, at=(0.5, 0.5), section="details"),
    ],
)
def test_gesture_rejects_unsupported_system_window_requests(gesture_request):
    screen = MagicMock(spec=DeviceScreen)

    with pytest.raises(LiveError, match="while a system window is in front"):
        SystemWindow(screen, "com.example.app").gesture(gesture_request)


def test_tap_text_uses_the_device_and_returns_connector_event_shape():
    screen = MagicMock(spec=DeviceScreen)
    request = InputRequest(InputKind.TAP_TEXT, text="USE THIS FOLDER", match=TextMatch.EXACT)

    event = SystemWindow(screen, "com.example.app").tap_text(request)

    screen.tap_text.assert_called_once_with("USE THIS FOLDER", TextMatch.EXACT, None)
    assert event == DemoEvent(event="text_tapped", demo=None, name=None, hwnd=None)


def test_shot_saves_device_capture_bytes(tmp_path: Path):
    screen = MagicMock(spec=DeviceScreen)
    screen.capture_png.return_value = b"device-png"
    request = ShotRequest(None, tmp_path / "system.png")

    result = SystemWindow(screen, "com.example.app").shot(request)

    assert result == tmp_path / "system.png"
    assert result.read_bytes() == b"device-png"


@pytest.mark.parametrize(
    "shot_request",
    [
        ShotRequest("home", "out.png"),
        ShotRequest(None, "out.png", theme=ShotTheme.DARK),
    ],
)
def test_shot_rejects_options_that_need_the_app(shot_request):
    screen = MagicMock(spec=DeviceScreen)

    with pytest.raises(LiveError, match="while a system window is in front"):
        SystemWindow(screen, "com.example.app").shot(shot_request)

