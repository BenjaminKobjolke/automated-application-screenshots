"""Unit tests for PrintWindow-first window capture with the pyautogui fallback."""

from unittest.mock import MagicMock

import pytest
from PIL import Image

from screenshot_tool import capture
from screenshot_tool.capture import WindowCapture
from screenshot_tool.window_geometry import WindowGeometry

MAIN, POPUP = 1, 2
# Main window rect includes an invisible 8px resize border around the visible frame.
RECTS = {MAIN: (92, 192, 316, 416), POPUP: (150, 250, 160, 260)}
FRAME = (100, 200, 308, 408)


@pytest.fixture(autouse=True)
def geometry(monkeypatch):
    monkeypatch.setattr(WindowGeometry, "get_window_rect", lambda hwnd: RECTS[hwnd])
    monkeypatch.setattr(WindowGeometry, "get_extended_frame_bounds", lambda _hwnd: FRAME)
    monkeypatch.setattr(WindowGeometry, "get_work_area", lambda _hwnd: None)


@pytest.fixture
def screenshot(monkeypatch):
    grab = MagicMock(return_value=Image.new("RGB", (208, 208)))
    monkeypatch.setattr(capture.pyautogui, "screenshot", grab)
    return grab


def _renders(images: dict[int, Image.Image | None]):
    return lambda hwnd, _size: images[hwnd]


def test_capture_uses_print_window_cropped_to_visible_frame(screenshot, monkeypatch):
    full = Image.new("RGB", (224, 224), "black")
    full.paste(Image.new("RGB", (208, 208), "red"), (8, 8))
    monkeypatch.setattr(capture, "_print_window", _renders({MAIN: full}))
    monkeypatch.setattr(capture, "_windows_above", lambda _hwnd: [])

    image = WindowCapture.capture_window(MAIN)

    assert image.size == (208, 208)
    assert image.getcolors() == [(208 * 208, (255, 0, 0))]
    screenshot.assert_not_called()


@pytest.mark.usefixtures("screenshot")
def test_capture_pastes_same_process_popups_over_the_window(monkeypatch):
    renders = {MAIN: Image.new("RGB", (224, 224), "red"), POPUP: Image.new("RGB", (10, 10), "blue")}
    monkeypatch.setattr(capture, "_print_window", _renders(renders))
    monkeypatch.setattr(capture, "_windows_above", lambda _hwnd: [POPUP])

    image = WindowCapture.capture_window(MAIN)

    # Popup at screen (150, 250) lands at (50, 50) inside the visible frame
    assert image.getpixel((50, 50)) == (0, 0, 255)
    assert image.getpixel((60, 60)) == (255, 0, 0)


def test_capture_falls_back_to_screen_grab_when_print_window_fails(screenshot, monkeypatch):
    monkeypatch.setattr(capture, "_print_window", _renders({MAIN: None}))

    assert WindowCapture.capture_window(MAIN) is screenshot.return_value
    screenshot.assert_called_once_with(region=(100, 200, 208, 208))


def test_capture_rejects_empty_window(monkeypatch):
    monkeypatch.setattr(WindowGeometry, "get_extended_frame_bounds", lambda _hwnd: (5, 5, 5, 5))
    monkeypatch.setattr(WindowGeometry, "get_work_area", lambda _hwnd: None)

    with pytest.raises(RuntimeError, match="Invalid window dimensions"):
        WindowCapture.capture_window(MAIN)
