"""Focused tests for detecting slow Android package-manager responses."""

import subprocess
from unittest.mock import MagicMock

import pytest

from screenshot_tool.emulator_health import (
    SLOW_PACKAGE_MANAGER_SECONDS,
    package_manager_seconds,
    wait_until_disconnected,
)


def test_package_manager_seconds_times_the_adb_command() -> None:
    runner = MagicMock(spec=subprocess)
    runner.run.return_value = subprocess.CompletedProcess(
        [], 0, stdout="package:/system/framework/framework-res.apk\n"
    )

    seconds = package_manager_seconds(runner, "adb", "emulator-5554")

    assert seconds >= 0
    runner.run.assert_called_once_with(
        ["adb", "-s", "emulator-5554", "shell", "pm", "path", "android"],
        capture_output=True,
        check=False,
        text=True,
        timeout=SLOW_PACKAGE_MANAGER_SECONDS,
    )


def test_package_manager_seconds_returns_limit_when_adb_times_out() -> None:
    runner = MagicMock(spec=subprocess)
    runner.run.side_effect = subprocess.TimeoutExpired("adb", SLOW_PACKAGE_MANAGER_SECONDS)

    seconds = package_manager_seconds(runner, "adb", "emulator-5554")

    assert seconds >= SLOW_PACKAGE_MANAGER_SECONDS


def test_wait_until_disconnected_returns_when_serial_is_gone() -> None:
    list_serials = MagicMock(side_effect=[["emulator-5554"], []])

    wait_until_disconnected(list_serials, "emulator-5554", timeout=2)

    assert list_serials.call_count == 2
    assert all(call.args[0] > 0 for call in list_serials.call_args_list)


def test_wait_until_disconnected_bounds_serial_listing_timeout() -> None:
    list_serials = MagicMock(
        side_effect=subprocess.TimeoutExpired("adb devices", timeout=1)
    )

    with pytest.raises(TimeoutError, match="emulator-5554"):
        wait_until_disconnected(list_serials, "emulator-5554", timeout=1)
    assert 0 < list_serials.call_args.args[0] <= 1


def test_wait_until_disconnected_times_out_when_serial_stays_listed(monkeypatch) -> None:
    list_serials = MagicMock(return_value=["emulator-5554"])
    monkeypatch.setattr("screenshot_tool.emulator_health.time.sleep", lambda _: None)
    ticks = iter([0.0, 0.0, 0.5, 1.0, 1.0, 1.5, 2.0])
    monkeypatch.setattr("screenshot_tool.emulator_health.time.monotonic", lambda: next(ticks))

    with pytest.raises(TimeoutError, match="emulator-5554"):
        wait_until_disconnected(list_serials, "emulator-5554", timeout=1)
