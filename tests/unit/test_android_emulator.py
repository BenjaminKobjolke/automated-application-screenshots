"""Focused tests for Android emulator discovery and ownership."""

import subprocess
import pytest
from unittest.mock import MagicMock

from screenshot_tool.android_emulator import AndroidEmulator


def completed(stdout: str = "", returncode: int = 0) -> subprocess.CompletedProcess[str]:
    return subprocess.CompletedProcess([], returncode, stdout=stdout, stderr="")


def test_running_serials_parses_only_online_emulators():
    runner = MagicMock(spec=subprocess)
    runner.run.return_value = completed(
        "List of devices attached\n"
        "emulator-5554\tdevice product:sdk_gphone64\n"
        "emulator-5556\toffline\n"
        "R5CT123\tdevice product:phone\n"
    )
    emulator = AndroidEmulator(runner=runner)

    assert emulator.running_serials() == ["emulator-5554"]
    runner.run.assert_called_once_with(
        ["adb", "devices"], capture_output=True, check=True, text=True
    )


def test_ensure_reuses_running_emulator_without_starting_one():
    runner = MagicMock(spec=subprocess)
    runner.run.side_effect = [
        completed("List of devices attached\nemulator-5556\tdevice\n"),
        completed(),
        completed("1\n"),
    ]
    emulator = AndroidEmulator(runner=runner)

    assert emulator.ensure("Pixel_8_API_35", headless=True, timeout=5) == "emulator-5556"
    runner.Popen.assert_not_called()


def test_ensure_starts_and_owns_headless_emulator():
    runner = MagicMock(spec=subprocess)
    runner.run.side_effect = [
        completed("List of devices attached\n"),
        completed("List of devices attached\nemulator-5554\tdevice\n"),
        completed(),
        completed("1\n"),
        completed(),
    ]
    process = MagicMock(spec=subprocess.Popen)
    process.pid = 123
    process.poll.return_value = None
    runner.Popen.return_value = process
    emulator = AndroidEmulator(runner=runner)

    assert emulator.ensure("Pixel_8_API_35", headless=True, timeout=5) == "emulator-5554"
    runner.Popen.assert_called_once_with(
        ["emulator", "-avd", "Pixel_8_API_35", "-no-window", "-no-snapshot-save"],
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )
    emulator.stop()
    runner.run.assert_any_call(
        ["adb", "-s", "emulator-5554", "emu", "kill"],
        capture_output=True,
        check=False,
        text=True,
    )


def test_stop_leaves_reused_emulator_running():
    runner = MagicMock(spec=subprocess)
    emulator = AndroidEmulator(runner=runner)
    emulator._serial = "emulator-5554"

    emulator.stop()

    runner.run.assert_not_called()
    runner.Popen.assert_not_called()


def test_wait_for_device_is_bounded_by_remaining_boot_timeout():
    runner = MagicMock(spec=subprocess)
    runner.run.side_effect = [
        completed("List of devices attached\nemulator-5554\tdevice\n"),
        subprocess.TimeoutExpired(["adb", "wait-for-device"], 2),
    ]
    emulator = AndroidEmulator(runner=runner)

    with pytest.raises(TimeoutError, match="did not become available"):
        emulator.ensure("Pixel_8_API_35", headless=False, timeout=2)

    args, kwargs = runner.run.call_args_list[1]
    assert args[0] == ["adb", "-s", "emulator-5554", "wait-for-device"]
    assert 0 < kwargs["timeout"] <= 2
