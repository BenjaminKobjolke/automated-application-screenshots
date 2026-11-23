"""Tests for emulator startup, recovery, and rotation behavior."""

import os
import subprocess
from pathlib import Path
from unittest.mock import MagicMock

import pytest
from android_fakes import completed, env_with_sdk, fake_sdk

from screenshot_tool import emulator_health
from screenshot_tool.android_emulator import AndroidEmulator
from screenshot_tool.emulator_rotation import EmulatorRotation


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


def test_ensure_restarts_degraded_reused_emulator_and_owns_restart(tmp_path: Path):
    sdk = fake_sdk(tmp_path / "sdk")
    adb = str(sdk / "platform-tools" / ("adb.exe" if os.name == "nt" else "adb"))
    runner = MagicMock(spec=subprocess)
    runner.run.side_effect = [
        completed("List of devices attached\nemulator-5554\tdevice\n"),
        completed("Pixel_9_Demos\n"),
        completed(),
        completed("1\n"),
        subprocess.TimeoutExpired([adb, "shell", "pm", "path", "android"], 10),
        completed(),
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
    emulator = AndroidEmulator(runner=runner, environ=env_with_sdk(sdk))

    assert emulator.ensure("Pixel_9_Demos", headless=True, timeout=5) == "emulator-5554"

    runner.Popen.assert_called_once()
    assert runner.Popen.call_args.args[0][1:3] == ["-avd", "Pixel_9_Demos"]
    assert runner.Popen.call_args.args[0][-3:] == [
        "-no-snapshot-save",
        "-crash-report-mode",
        "disabled",
    ]
    emulator.stop()
    assert runner.run.call_args_list[-1].args[0][-2:] == ["emu", "kill"]


def test_ensure_restarts_degraded_reused_emulator_using_discovered_avd(tmp_path: Path):
    sdk = fake_sdk(tmp_path / "sdk")
    adb = str(sdk / "platform-tools" / ("adb.exe" if os.name == "nt" else "adb"))
    runner = MagicMock(spec=subprocess)
    runner.run.side_effect = [
        completed("List of devices attached\nemulator-5554\tdevice\n"),
        completed(),
        completed("1\n"),
        subprocess.TimeoutExpired([adb, "shell", "pm", "path", "android"], 10),
        completed("Pixel_9_Demos\n"),
        completed(),
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

    assert emulator.ensure(None, headless=False, timeout=5) == "emulator-5554"

    assert runner.Popen.call_args.args[0][1:3] == ["-avd", "Pixel_9_Demos"]


def test_ensure_fails_fast_when_degraded_emulator_avd_is_unknown(tmp_path: Path):
    sdk = fake_sdk(tmp_path / "sdk")
    adb = str(sdk / "platform-tools" / ("adb.exe" if os.name == "nt" else "adb"))
    runner = MagicMock(spec=subprocess)
    runner.run.side_effect = [
        completed("List of devices attached\nemulator-5554\tdevice\n"),
        completed(),
        completed("1\n"),
        subprocess.TimeoutExpired([adb, "shell", "pm", "path", "android"], 10),
        completed("\n"),
    ]
    emulator = AndroidEmulator(runner=runner, environ=env_with_sdk(sdk))

    with pytest.raises(RuntimeError) as error:
        emulator.ensure(None, headless=True, timeout=5)

    assert all(
        part in str(error.value).lower() for part in ("emulator-5554", "10", "restart", "close")
    )
    runner.Popen.assert_not_called()


def test_ensure_fails_fast_when_degraded_emulator_does_not_disconnect(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
):
    sdk = fake_sdk(tmp_path / "sdk")
    adb = str(sdk / "platform-tools" / ("adb.exe" if os.name == "nt" else "adb"))
    runner = MagicMock(spec=subprocess)
    runner.run.side_effect = [
        completed("List of devices attached\nemulator-5554\tdevice\n"),
        completed("Pixel_9_Demos\n"),
        completed(),
        completed("1\n"),
        subprocess.TimeoutExpired([adb, "shell", "pm", "path", "android"], 10),
        completed(),
    ]
    monkeypatch.setattr(
        emulator_health,
        "wait_until_disconnected",
        lambda *_args, **_kwargs: (_ for _ in ()).throw(TimeoutError("still listed")),
    )
    emulator = AndroidEmulator(runner=runner, environ=env_with_sdk(sdk))

    with pytest.raises(RuntimeError) as error:
        emulator.ensure("Pixel_9_Demos", headless=True, timeout=5)

    assert all(
        part in str(error.value).lower()
        for part in ("emulator-5554", "pixel_9_demos", "10", "close")
    )
    runner.Popen.assert_not_called()


def test_ensure_does_not_restart_healthy_reused_emulator(tmp_path: Path):
    sdk = fake_sdk(tmp_path / "sdk")
    runner = MagicMock(spec=subprocess)
    runner.run.side_effect = [
        completed("List of devices attached\nemulator-5554\tdevice\n"),
        completed("Pixel_9_Demos\n"),
        completed(),
        completed("1\n"),
        completed("package:/system/framework/framework-res.apk\n"),
        completed("0\n"),
        completed(),
        completed(),
        completed(),
    ]
    emulator = AndroidEmulator(runner=runner, environ=env_with_sdk(sdk))

    assert emulator.ensure("Pixel_9_Demos", headless=True, timeout=5) == "emulator-5554"

    runner.Popen.assert_not_called()
    assert not any(call.args[0][-2:] == ["emu", "kill"] for call in runner.run.call_args_list)
