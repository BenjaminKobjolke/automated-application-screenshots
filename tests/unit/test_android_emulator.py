"""Focused tests for Android emulator discovery and ownership."""

import os
import subprocess
from pathlib import Path
from unittest.mock import MagicMock

import pytest
from android_fakes import completed, env_with_sdk, fake_sdk

from screenshot_tool.android_emulator import AndroidEmulator
from screenshot_tool.emulator_rotation import EmulatorRotation


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
        completed("Pixel_8_API_35\n"),
        completed(),
        completed("1\n"),
        completed("0\n"),
        completed(),
        completed(),
        completed(),
    ]
    emulator = AndroidEmulator(runner=runner, environ=env_with_sdk(sdk))

    assert emulator.ensure("Pixel_8_API_35", headless=True, timeout=5) == "emulator-5556"
    runner.Popen.assert_not_called()


def test_ensure_keeps_screen_awake_after_boot(tmp_path: Path):
    sdk = fake_sdk(tmp_path / "sdk")
    runner = MagicMock(spec=subprocess)
    runner.run.side_effect = [
        completed("List of devices attached\nemulator-5554\tdevice\n"),
        completed(),
        completed("1\n"),
        completed("0\n"),
        completed(),
        completed(),
        completed(),
    ]
    emulator = AndroidEmulator(runner=runner, environ=env_with_sdk(sdk))

    assert emulator.ensure(None, headless=False, timeout=5) == "emulator-5554"

    adb = str(sdk / "platform-tools" / ("adb.exe" if os.name == "nt" else "adb"))
    assert [call.args[0] for call in runner.run.call_args_list[3:]] == [
        [adb, "-s", "emulator-5554", "shell", "settings", "get", "global", "stay_on_while_plugged_in"],
        [adb, "-s", "emulator-5554", "shell", "svc", "power", "stayon", "true"],
        [adb, "-s", "emulator-5554", "shell", "input", "keyevent", "KEYCODE_WAKEUP"],
        [adb, "-s", "emulator-5554", "shell", "wm", "dismiss-keyguard"],
    ]


@pytest.mark.parametrize(
    ("saved_value", "restore_operation", "restore_value"),
    [("0", "put", "0"), ("null", "delete", None)],
)
def test_stop_restores_stay_on_setting_of_reused_emulator(
    tmp_path: Path, saved_value: str, restore_operation: str, restore_value: str | None
):
    sdk = fake_sdk(tmp_path / "sdk")
    runner = MagicMock(spec=subprocess)
    runner.run.side_effect = [
        completed("List of devices attached\nemulator-5554\tdevice\n"),
        completed(),
        completed("1\n"),
        completed(f"{saved_value}\n"),
        completed(),
        completed(),
        completed(),
        completed(),
    ]
    emulator = AndroidEmulator(runner=runner, environ=env_with_sdk(sdk))
    emulator.ensure(None, headless=False, timeout=5)

    emulator.stop()

    restore = runner.run.call_args_list[-1]
    expected_restore = [
        str(sdk / "platform-tools" / ("adb.exe" if os.name == "nt" else "adb")),
        "-s",
        "emulator-5554",
        "shell",
        "settings",
        restore_operation,
        "global",
        "stay_on_while_plugged_in",
    ]
    if restore_value is not None:
        expected_restore.append(restore_value)
    assert restore.args[0] == expected_restore
    assert restore.kwargs == {"capture_output": True, "check": False, "text": True}
    assert not any("emu" in call.args[0] for call in runner.run.call_args_list[-1:])


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


def test_stop_leaves_reused_emulator_running():
    runner = MagicMock(spec=subprocess)
    emulator = AndroidEmulator(runner=runner)
    emulator._serial = "emulator-5554"

    emulator.stop()

    runner.run.assert_not_called()
    runner.Popen.assert_not_called()


def test_rotation_requires_a_started_emulator_and_uses_its_adb_path(tmp_path: Path):
    sdk = fake_sdk(tmp_path / "sdk")
    runner = MagicMock(spec=subprocess)
    emulator = AndroidEmulator(runner=runner, environ=env_with_sdk(sdk))

    with pytest.raises(RuntimeError, match="emulator is not started"):
        emulator.rotation()

    emulator._serial = "emulator-5554"
    rotation = emulator.rotation()

    assert isinstance(rotation, EmulatorRotation)
    assert rotation._adb == str(sdk / "platform-tools" / ("adb.exe" if os.name == "nt" else "adb"))


def test_wait_for_device_is_bounded_by_remaining_boot_timeout(tmp_path: Path):
    sdk = fake_sdk(tmp_path / "sdk")
    runner = MagicMock(spec=subprocess)
    runner.run.side_effect = [
        completed("List of devices attached\nemulator-5554\tdevice\n"),
        subprocess.TimeoutExpired(["adb", "wait-for-device"], 2),
    ]
    emulator = AndroidEmulator(runner=runner, environ=env_with_sdk(sdk))

    with pytest.raises(TimeoutError, match="did not become available"):
        emulator.ensure(None, headless=False, timeout=2)

    args, kwargs = runner.run.call_args_list[1]
    assert args[0][0] == str(sdk / "platform-tools" / ("adb.exe" if os.name == "nt" else "adb"))
    assert args[0][1:] == ["-s", "emulator-5554", "wait-for-device"]
    assert 0 < kwargs["timeout"] <= 2
