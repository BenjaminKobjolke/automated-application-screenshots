"""Focused tests for Android emulator discovery and ownership."""

import os
import subprocess
from pathlib import Path
from unittest.mock import MagicMock

import pytest
from android_fakes import completed, env_with_sdk, fake_sdk

from screenshot_tool.android_emulator import AndroidEmulator


def test_running_serials_parses_only_online_emulators(tmp_path: Path):
    sdk = fake_sdk(tmp_path / "sdk")
    runner = MagicMock(spec=subprocess)
    runner.run.return_value = completed(
        "List of devices attached\n"
        "emulator-5554\tdevice product:sdk_gphone64\n"
        "emulator-5556\toffline\n"
        "R5CT123\tdevice product:phone\n"
    )
    emulator = AndroidEmulator(runner=runner, environ=env_with_sdk(sdk))

    assert emulator.running_serials() == ["emulator-5554"]
    runner.run.assert_called_once_with(
        [str(sdk / "platform-tools" / ("adb.exe" if os.name == "nt" else "adb")), "devices"],
        capture_output=True,
        check=True,
        text=True,
    )


def test_ensure_reuses_running_emulator_without_starting_one(tmp_path: Path):
    sdk = fake_sdk(tmp_path / "sdk")
    runner = MagicMock(spec=subprocess)
    runner.run.side_effect = [
        completed("List of devices attached\nemulator-5556\tdevice\n"),
        completed(),
        completed("1\n"),
    ]
    emulator = AndroidEmulator(runner=runner, environ=env_with_sdk(sdk))

    assert emulator.ensure("Pixel_8_API_35", headless=True, timeout=5) == "emulator-5556"
    runner.Popen.assert_not_called()


def test_ensure_starts_and_owns_headless_emulator(tmp_path: Path):
    sdk = fake_sdk(tmp_path / "sdk")
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
    emulator = AndroidEmulator(runner=runner, environ=env_with_sdk(sdk))

    assert emulator.ensure("Pixel_8_API_35", headless=True, timeout=5) == "emulator-5554"
    runner.Popen.assert_called_once_with(
        [
            str(sdk / "emulator" / ("emulator.exe" if os.name == "nt" else "emulator")),
            "-avd",
            "Pixel_8_API_35",
            "-no-window",
            "-no-snapshot-save",
            "-crash-report-mode",
            "disabled",
        ],
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )
    emulator.stop()
    runner.run.assert_any_call(
        [
            str(sdk / "platform-tools" / ("adb.exe" if os.name == "nt" else "adb")),
            "-s",
            "emulator-5554",
            "emu",
            "kill",
        ],
        capture_output=True,
        check=False,
        text=True,
    )


def test_ensure_disables_crash_report_prompt_with_window(tmp_path: Path):
    sdk = fake_sdk(tmp_path / "sdk")
    runner = MagicMock(spec=subprocess)
    runner.run.side_effect = [
        completed("List of devices attached\n"),
        completed("List of devices attached\nemulator-5554\tdevice\n"),
        completed(),
        completed("1\n"),
    ]
    process = MagicMock(spec=subprocess.Popen)
    process.pid = 123
    process.poll.return_value = None
    runner.Popen.return_value = process
    emulator = AndroidEmulator(runner=runner, environ=env_with_sdk(sdk))

    assert emulator.ensure("Pixel_8_API_35", headless=False, timeout=5) == "emulator-5554"

    command = runner.Popen.call_args.args[0]
    flag_index = command.index("-crash-report-mode")
    assert command[flag_index : flag_index + 2] == ["-crash-report-mode", "disabled"]
    assert "-no-window" not in command


def test_stop_leaves_reused_emulator_running():
    runner = MagicMock(spec=subprocess)
    emulator = AndroidEmulator(runner=runner)
    emulator._serial = "emulator-5554"

    emulator.stop()

    runner.run.assert_not_called()
    runner.Popen.assert_not_called()


def test_wait_for_device_is_bounded_by_remaining_boot_timeout(tmp_path: Path):
    sdk = fake_sdk(tmp_path / "sdk")
    runner = MagicMock(spec=subprocess)
    runner.run.side_effect = [
        completed("List of devices attached\nemulator-5554\tdevice\n"),
        subprocess.TimeoutExpired(["adb", "wait-for-device"], 2),
    ]
    emulator = AndroidEmulator(runner=runner, environ=env_with_sdk(sdk))

    with pytest.raises(TimeoutError, match="did not become available"):
        emulator.ensure("Pixel_8_API_35", headless=False, timeout=2)

    args, kwargs = runner.run.call_args_list[1]
    assert args[0][0] == str(
        sdk / "platform-tools" / ("adb.exe" if os.name == "nt" else "adb")
    )
    assert args[0][1:] == ["-s", "emulator-5554", "wait-for-device"]
    assert 0 < kwargs["timeout"] <= 2
