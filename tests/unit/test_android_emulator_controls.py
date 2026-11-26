"""Focused tests for emulator controls and reverse-port cleanup."""

import os
import subprocess
from pathlib import Path
from unittest.mock import MagicMock

import pytest
from android_fakes import env_with_sdk, fake_sdk

from screenshot_tool.android_emulator import AndroidEmulator


def test_reverse_port_runs_adb_reverse_for_selected_serial(tmp_path: Path):
    sdk = fake_sdk(tmp_path / "sdk")
    runner = MagicMock(spec=subprocess)
    emulator = AndroidEmulator(runner=runner, environ=env_with_sdk(sdk))
    emulator._serial = "emulator-5554"

    emulator.reverse_port(8766)

    adb = str(sdk / "platform-tools" / ("adb.exe" if os.name == "nt" else "adb"))
    runner.run.assert_called_once_with(
        [adb, "-s", "emulator-5554", "reverse", "tcp:8766", "tcp:8766"],
        capture_output=True,
        check=True,
        text=True,
    )


def test_reverse_port_requires_a_started_emulator():
    emulator = AndroidEmulator(runner=MagicMock(spec=subprocess))

    with pytest.raises(RuntimeError, match="emulator is not started"):
        emulator.reverse_port(8766)


def test_stop_removes_reverse_of_reused_emulator(tmp_path: Path):
    sdk = fake_sdk(tmp_path / "sdk")
    runner = MagicMock(spec=subprocess)
    emulator = AndroidEmulator(runner=runner, environ=env_with_sdk(sdk))
    emulator._serial = "emulator-5554"
    emulator.reverse_port(8766)

    emulator.stop()

    remove = runner.run.call_args_list[-1]
    assert remove.args[0] == [
        str(sdk / "platform-tools" / ("adb.exe" if os.name == "nt" else "adb")),
        "-s",
        "emulator-5554",
        "reverse",
        "--remove",
        "tcp:8766",
    ]
    assert remove.kwargs == {"capture_output": True, "check": False, "text": True}
    assert not any("emu" in call.args[0] for call in runner.run.call_args_list)


def test_stop_removes_reverse_before_killing_owned_emulator(tmp_path: Path):
    sdk = fake_sdk(tmp_path / "sdk")
    runner = MagicMock(spec=subprocess)
    emulator = AndroidEmulator(runner=runner, environ=env_with_sdk(sdk))
    emulator._serial = "emulator-5554"
    emulator._owns_emulator = True
    emulator.reverse_port(8766)

    emulator.stop()

    calls = [call.args[0] for call in runner.run.call_args_list]
    remove = calls.index(
        [
            str(sdk / "platform-tools" / ("adb.exe" if os.name == "nt" else "adb")),
            "-s",
            "emulator-5554",
            "reverse",
            "--remove",
            "tcp:8766",
        ]
    )
    kill = calls.index(
        [
            str(sdk / "platform-tools" / ("adb.exe" if os.name == "nt" else "adb")),
            "-s",
            "emulator-5554",
            "emu",
            "kill",
        ]
    )
    assert remove < kill


def test_stop_without_reverse_runs_no_remove():
    runner = MagicMock(spec=subprocess)
    emulator = AndroidEmulator(runner=runner)
    emulator._serial = "emulator-5554"

    emulator.stop()

    assert not any("reverse" in call.args[0] for call in runner.run.call_args_list)


def test_device_screen_uses_selected_serial_and_adb_path(tmp_path: Path):
    sdk = fake_sdk(tmp_path / "sdk")
    runner = MagicMock(spec=subprocess)
    emulator = AndroidEmulator(runner=runner, environ=env_with_sdk(sdk))
    emulator._serial = "emulator-5554"

    screen = emulator.device_screen()

    assert screen._serial == "emulator-5554"
    assert screen._adb == str(
        sdk / "platform-tools" / ("adb.exe" if os.name == "nt" else "adb")
    )
    assert screen._runner is runner


def test_device_screen_requires_a_started_emulator():
    emulator = AndroidEmulator(runner=MagicMock(spec=subprocess))

    with pytest.raises(RuntimeError, match="emulator is not started"):
        emulator.device_screen()
