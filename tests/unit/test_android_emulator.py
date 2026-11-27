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
        completed("Pixel_8_API_35\n"),
        completed(),
        completed("1\n"),
        completed("package:/system/framework/framework-res.apk\n"),
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
        completed("package:/system/framework/framework-res.apk\n"),
        completed("0\n"),
        completed(),
        completed(),
        completed(),
    ]
    emulator = AndroidEmulator(runner=runner, environ=env_with_sdk(sdk))

    assert emulator.ensure(None, headless=False, timeout=5) == "emulator-5554"

    adb = str(sdk / "platform-tools" / ("adb.exe" if os.name == "nt" else "adb"))
    assert [call.args[0] for call in runner.run.call_args_list[4:]] == [
        [
            adb,
            "-s",
            "emulator-5554",
            "shell",
            "settings",
            "get",
            "global",
            "stay_on_while_plugged_in",
        ],
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
        completed("package:/system/framework/framework-res.apk\n"),
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


def test_stop_leaves_reused_emulator_running():
    runner = MagicMock(spec=subprocess)
    emulator = AndroidEmulator(runner=runner)
    emulator._serial = "emulator-5554"

    emulator.stop()

    runner.run.assert_not_called()
    runner.Popen.assert_not_called()


def test_device_state_reports_adb_and_owned_process_state():
    runner = MagicMock(spec=subprocess)
    emulator = AndroidEmulator(runner=runner)
    emulator._serial = "emulator-5554"
    emulator._owns_emulator = True
    emulator._process = MagicMock(spec=subprocess.Popen)
    emulator._process.poll.return_value = 17
    emulator.running_serials = MagicMock(return_value=[])

    assert emulator.device_state() == (
        "emulator-5554 is not listed by adb; emulator process exited with code 17"
    )


def test_device_state_reports_listed_emulator():
    runner = MagicMock(spec=subprocess)
    emulator = AndroidEmulator(runner=runner)
    emulator._serial = "emulator-5554"
    emulator.running_serials = MagicMock(return_value=["emulator-5554"])

    assert emulator.device_state() == "emulator-5554 is still listed by adb"


def test_logcat_stops_without_shutting_down_reused_emulator(tmp_path, monkeypatch):
    from screenshot_tool import android_emulator_lifecycle

    runner = MagicMock(spec=subprocess)
    logcat_process = MagicMock(spec=subprocess.Popen)
    logcat_process.poll.return_value = None
    runner.Popen.return_value = logcat_process
    emulator = AndroidEmulator(runner=runner, log_dir=tmp_path / "session")
    emulator.running_serials = MagicMock(return_value=["emulator-5554"])
    emulator.avd_name = MagicMock(return_value="Pixel_9")
    emulator._wait_for_boot = MagicMock()
    emulator._keep_awake = MagicMock()
    monkeypatch.setattr(android_emulator_lifecycle, "package_manager_seconds", lambda *_args: 0)

    emulator.ensure("Pixel_9", headless=False, timeout=5)
    emulator.stop()

    logcat_process.terminate.assert_called_once_with()
    assert not any("emu" in call.args[0] for call in runner.run.call_args_list)
