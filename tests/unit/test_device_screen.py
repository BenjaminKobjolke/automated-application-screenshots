"""Tests for reading and controlling Android system windows through adb."""

import subprocess
from unittest.mock import MagicMock

import pytest

from screenshot_tool.live_types import LiveError


def test_parse_foreground_package_reads_top_resumed_activity():
    from screenshot_tool.device_screen import parse_foreground_package

    output = (
        "topResumedActivity=ActivityRecord{1a2b u0 "
        "com.google.android.documentsui/com.android.documentsui.picker.PickActivity t12}"
    )

    assert parse_foreground_package(output) == "com.google.android.documentsui"


def test_parse_foreground_package_reads_older_resumed_activity_form():
    from screenshot_tool.device_screen import parse_foreground_package

    output = "mResumedActivity: ActivityRecord{123 u0 com.example.app/.Main t4}"

    assert parse_foreground_package(output) == "com.example.app"


def test_parse_foreground_package_returns_none_without_activity():
    from screenshot_tool.device_screen import parse_foreground_package

    assert parse_foreground_package("no resumed activity") is None


def test_find_text_node_matches_exact_text_or_content_description():
    from screenshot_tool.device_screen import find_text_node

    xml = """<hierarchy>
      <node text="Documents" content-desc="" bounds="[10,20][110,60]" />
      <node text="" content-desc="USE THIS FOLDER" bounds="[20,80][220,120]" />
    </hierarchy>"""

    assert find_text_node(xml, "Documents", None, None).center == (60, 40)
    assert find_text_node(xml, "USE THIS FOLDER", None, None).label == "USE THIS FOLDER"


def test_find_text_node_matches_content_description_when_text_is_also_present():
    from screenshot_tool.device_screen import find_text_node

    xml = '<node text="Button" content-desc="Open folder" bounds="[10,20][110,60]" />'

    node = find_text_node(xml, "Open folder", None, None)

    assert node.label == "Button"
    assert node.center == (60, 40)


def test_find_text_node_supports_contains_and_index():
    from screenshot_tool.device_screen import find_text_node
    from screenshot_tool.live_input import TextMatch

    xml = """<hierarchy>
      <node text="Documents" content-desc="" bounds="[0,0][20,20]" />
      <node text="Documents from SD card" content-desc="" bounds="[20,0][40,20]" />
    </hierarchy>"""

    node = find_text_node(xml, "Documents", TextMatch.CONTAINS, 1)
    assert node.label == "Documents from SD card"
    assert node.center == (30, 10)


def test_find_text_node_reports_visible_labels_when_missing():
    from screenshot_tool.device_screen import find_text_node

    xml = '<node text="Documents" bounds="[0,0][20,20]" />'

    with pytest.raises(LiveError, match="Documents"):
        find_text_node(xml, "Missing", None, None)


def test_find_text_node_requires_index_for_ambiguous_matches():
    from screenshot_tool.device_screen import find_text_node

    xml = """<hierarchy>
      <node text="Documents" bounds="[0,0][20,20]" />
      <node text="Documents" bounds="[20,0][40,20]" />
    </hierarchy>"""

    with pytest.raises(LiveError, match="index"):
        find_text_node(xml, "Documents", None, None)


def test_capture_png_uses_binary_adb_and_checks_signature():
    from screenshot_tool.device_screen import DeviceScreen

    runner = MagicMock(spec=subprocess)
    runner.run.return_value = subprocess.CompletedProcess([], 0, stdout=b"\x89PNG\r\n\x1a\nimage")
    screen = DeviceScreen(runner, "adb", "emulator-5554")

    assert screen.capture_png() == b"\x89PNG\r\n\x1a\nimage"
    args, kwargs = runner.run.call_args
    assert args[0] == ["adb", "-s", "emulator-5554", "exec-out", "screencap", "-p"]
    assert kwargs["text"] is False
    assert kwargs["timeout"] == 30.0


def test_device_screen_adb_timeout_names_command():
    from screenshot_tool.device_screen import DeviceScreen

    runner = MagicMock(spec=subprocess)
    runner.run.side_effect = subprocess.TimeoutExpired(
        ["adb", "-s", "emulator-5554", "shell", "dumpsys", "activity"], 30
    )
    screen = DeviceScreen(runner, "adb", "emulator-5554")

    with pytest.raises(LiveError, match=r"adb.*dumpsys.*activity"):
        screen.foreground_package()


def test_capture_png_rejects_non_png_data():
    from screenshot_tool.device_screen import DeviceScreen

    runner = MagicMock(spec=subprocess)
    runner.run.return_value = subprocess.CompletedProcess([], 0, stdout=b"not an image")
    screen = DeviceScreen(runner, "adb", "emulator-5554")

    with pytest.raises(LiveError, match="PNG"):
        screen.capture_png()


def test_capture_png_adb_timeout_names_command():
    from screenshot_tool.device_screen import DeviceScreen

    runner = MagicMock(spec=subprocess)
    runner.run.side_effect = subprocess.TimeoutExpired(
        ["adb", "-s", "emulator-5554", "exec-out", "screencap", "-p"], 30
    )
    screen = DeviceScreen(runner, "adb", "emulator-5554")

    with pytest.raises(LiveError, match=r"adb.*screencap"):
        screen.capture_png()


@pytest.mark.parametrize(
    ("rotation", "expected"),
    [(0, (270, 576)), (1, (600, 259)), (3, (600, 259))],
)
def test_tap_maps_screen_fractions_to_pixels(rotation, expected):
    from screenshot_tool.device_screen import DeviceScreen

    runner = MagicMock(spec=subprocess)
    runner.run.side_effect = [
        subprocess.CompletedProcess([], 0, stdout="Physical size: 1080x2400\n"),
        subprocess.CompletedProcess(
            [], 0, stdout=f"mOverrideDisplayInfo=DisplayInfo{{rotation {rotation}}}"
        ),
        subprocess.CompletedProcess([], 0, stdout=""),
    ]
    screen = DeviceScreen(runner, "adb", "emulator-5554")

    screen.tap(0.25, 0.24)

    assert runner.run.call_args.args[0][-4:] == ["input", "tap", str(expected[0]), str(expected[1])]


def test_swipe_maps_fractions_and_uses_default_duration():
    from screenshot_tool.device_screen import DeviceScreen

    runner = MagicMock(spec=subprocess)
    runner.run.side_effect = [
        subprocess.CompletedProcess([], 0, stdout="Physical size: 1080x2400\n"),
        subprocess.CompletedProcess(
            [], 0, stdout="mOverrideDisplayInfo=DisplayInfo{rotation 0}"
        ),
        subprocess.CompletedProcess([], 0, stdout="Physical size: 1080x2400\n"),
        subprocess.CompletedProcess(
            [], 0, stdout="mOverrideDisplayInfo=DisplayInfo{rotation 0}"
        ),
        subprocess.CompletedProcess([], 0, stdout=""),
    ]
    screen = DeviceScreen(runner, "adb", "emulator-5554")

    screen.swipe((0.1, 0.2), (0.8, 0.9), None)

    assert runner.run.call_args.args[0][-7:] == [
        "input",
        "swipe",
        "108",
        "480",
        "864",
        "2160",
        "300",
    ]

