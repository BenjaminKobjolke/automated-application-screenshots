"""Tests for Android display orientation parsing and restoration."""

import subprocess
from unittest.mock import MagicMock

import pytest
from android_fakes import completed

from screenshot_tool.emulator_rotation import (
    EmulatorRotation,
    parse_display_rotation,
    parse_wm_size,
)


def test_parse_wm_size_uses_override_size_when_available():
    assert parse_wm_size("Physical size: 1080x2400\nOverride size: 1600x2560\n") == (
        1600,
        2560,
    )


def test_parse_wm_size_uses_physical_size_without_override():
    assert parse_wm_size("Physical size: 1080x2400\n") == (1080, 2400)


def test_parse_display_rotation_reads_override_display_info():
    assert (
        parse_display_rotation(
            "mOverrideDisplayInfo=DisplayInfo{rotation 3, logicalWidth 1080, logicalHeight 2400}"
        )
        == 3
    )


@pytest.mark.parametrize(
    ("size", "landscape", "expected_rotation"),
    [
        ("1080x2400", True, "1"),
        ("2560x1600", True, "0"),
        ("2560x1600", False, "1"),
    ],
)
def test_locked_sets_orientation_relative_to_natural_size(
    monkeypatch, size: str, landscape: bool, expected_rotation: str
):
    from screenshot_tool import emulator_rotation

    monkeypatch.setattr(emulator_rotation.time, "sleep", lambda _seconds: None)
    runner = MagicMock(spec=subprocess)
    runner.run.side_effect = [
        completed("1\n"),
        completed("0\n"),
        completed("mOverrideDisplayInfo=DisplayInfo{rotation 0}\n"),
        completed(f"Physical size: {size}\n"),
        completed(),
        completed(),
        completed("mOverrideDisplayInfo=DisplayInfo{rotation " + expected_rotation + "}\n"),
        completed(),
        completed(),
        completed("mOverrideDisplayInfo=DisplayInfo{rotation 0}\n"),
    ]
    rotation = EmulatorRotation(runner, "adb", "emulator-5554")

    with rotation.locked(landscape=landscape, timeout=1):
        pass

    assert runner.run.call_args_list[5].args[0][-1] == expected_rotation
    assert runner.run.call_args_list[7].args[0][-1] == "1"
    assert runner.run.call_args_list[8].args[0][-1] == "0"


def test_locked_restores_settings_when_body_raises(monkeypatch):
    from screenshot_tool import emulator_rotation

    monkeypatch.setattr(emulator_rotation.time, "sleep", lambda _seconds: None)
    runner = MagicMock(spec=subprocess)
    runner.run.side_effect = [
        completed("1\n"),
        completed("0\n"),
        completed("mOverrideDisplayInfo=DisplayInfo{rotation 0}\n"),
        completed("Physical size: 1080x2400\n"),
        completed(),
        completed(),
        completed("mOverrideDisplayInfo=DisplayInfo{rotation 1}\n"),
        completed(),
        completed(),
        completed("mOverrideDisplayInfo=DisplayInfo{rotation 0}\n"),
    ]
    rotation = EmulatorRotation(runner, "adb", "emulator-5554")

    with pytest.raises(RuntimeError, match="body failed"):
        with rotation.locked(landscape=True, timeout=1):
            raise RuntimeError("body failed")

    assert runner.run.call_args_list[7].args[0][-1] == "1"
    assert runner.run.call_args_list[8].args[0][-1] == "0"


def test_locked_times_out_when_requested_rotation_never_appears(monkeypatch):
    from screenshot_tool import emulator_rotation

    monkeypatch.setattr(emulator_rotation.time, "sleep", lambda _seconds: None)
    runner = MagicMock(spec=subprocess)

    def run(args, **_kwargs):
        if args[-4:-1] == ["settings", "get", "system"]:
            return completed("1\n" if args[-1] == "accelerometer_rotation" else "0\n")
        if args[-2:] == ["wm", "size"]:
            return completed("Physical size: 1080x2400\n")
        if args[-2:] == ["dumpsys", "display"]:
            return completed("mOverrideDisplayInfo=DisplayInfo{rotation 0}\n")
        return completed()

    runner.run.side_effect = run
    rotation = EmulatorRotation(runner, "adb", "emulator-5554")

    with pytest.raises(TimeoutError, match="emulator-5554.*landscape"):
        with rotation.locked(landscape=True, timeout=0.01):
            pass


def test_parse_helpers_reject_missing_values():
    with pytest.raises(ValueError, match="size"):
        parse_wm_size("no dimensions")
    with pytest.raises(ValueError, match="rotation"):
        parse_display_rotation("no display info")
