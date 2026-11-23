"""Tests for launching and owning Android emulators."""

import os
import subprocess
from pathlib import Path
from unittest.mock import MagicMock

from android_fakes import completed, env_with_sdk, fake_sdk

from screenshot_tool.android_emulator import AndroidEmulator


def _owned_emulator(tmp_path: Path) -> tuple[MagicMock, AndroidEmulator]:
    sdk = fake_sdk(tmp_path / "sdk")
    runner = MagicMock(spec=subprocess)
    runner.run.side_effect = [
        completed("List of devices attached\n"),
        completed("List of devices attached\nemulator-5554\tdevice\n"),
        completed(),
        completed("1\n"),
        completed("0\n"),
        completed(),
        completed(),
        completed(),
        completed(),
    ]
    process = MagicMock(spec=subprocess.Popen)
    process.pid = 123
    process.poll.return_value = None
    runner.Popen.return_value = process
    return runner, AndroidEmulator(runner=runner, environ=env_with_sdk(sdk))


def test_stop_of_owned_emulator_skips_stay_on_restore(tmp_path: Path):
    runner, emulator = _owned_emulator(tmp_path)
    emulator.ensure("Pixel_8_API_35", headless=True, timeout=5)

    emulator.stop()

    commands = [call.args[0] for call in runner.run.call_args_list]
    assert commands[-1][-2:] == ["emu", "kill"]
    assert not any(command[-3:-1] == ["settings", "put"] for command in commands)


def test_ensure_starts_requested_avd_when_only_a_different_avd_is_running(tmp_path: Path):
    sdk = fake_sdk(tmp_path / "sdk")
    runner = MagicMock(spec=subprocess)
    runner.run.side_effect = [
        completed("List of devices attached\nemulator-5554\tdevice\n"),
        completed("Pixel_9\n"),
        completed("List of devices attached\nemulator-5554\tdevice\nemulator-5556\tdevice\n"),
        completed(),
        completed("1\n"),
        completed("0\n"),
        completed(),
        completed(),
        completed(),
    ]
    process = MagicMock(spec=subprocess.Popen)
    process.pid = 123
    process.poll.return_value = None
    runner.Popen.return_value = process
    emulator = AndroidEmulator(runner=runner, environ=env_with_sdk(sdk))

    assert emulator.ensure("Pixel_Tablet", headless=True, timeout=5) == "emulator-5556"
    assert runner.Popen.call_args.args[0][1:3] == ["-avd", "Pixel_Tablet"]


def test_ensure_without_avd_reuses_any_running_emulator(tmp_path: Path):
    sdk = fake_sdk(tmp_path / "sdk")
    runner = MagicMock(spec=subprocess)
    runner.run.side_effect = [
        completed("List of devices attached\nemulator-5554\tdevice\n"),
        completed(),
        completed("1\n"),
        completed("package:/system/framework/framework-res.apk\n"),
        completed("0\n"),
        completed(),
        completed(),
        completed(),
    ]
    emulator = AndroidEmulator(runner=runner, environ=env_with_sdk(sdk))

    assert emulator.ensure(None, headless=False, timeout=5) == "emulator-5554"
    runner.Popen.assert_not_called()


def test_ensure_starts_and_owns_headless_emulator(tmp_path: Path):
    sdk = tmp_path / "sdk"
    runner, emulator = _owned_emulator(tmp_path)

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
        completed("0\n"),
        completed(),
        completed(),
        completed(),
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
