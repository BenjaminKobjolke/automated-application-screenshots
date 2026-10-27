"""Android SDK discovery and required-program tests."""

import os
import subprocess
from pathlib import Path
from unittest.mock import MagicMock

import pytest
from android_fakes import completed, env_with_sdk, fake_sdk

from screenshot_tool.android_emulator import AndroidEmulator


def test_resolves_from_path_first(tmp_path: Path):
    path_dir = tmp_path / "path"
    path_dir.mkdir()
    sdk = fake_sdk(tmp_path / "sdk")
    suffix = ".exe" if os.name == "nt" else ""
    path_adb = path_dir / f"adb{suffix}"
    path_adb.touch()
    if os.name != "nt":
        path_adb.chmod(0o755)
    runner = MagicMock(spec=subprocess)
    runner.run.return_value = completed("List of devices attached\n")
    emulator = AndroidEmulator(
        runner=runner,
        environ={"PATH": str(path_dir), "ANDROID_HOME": str(sdk)},
    )

    emulator.running_serials()

    assert Path(runner.run.call_args.args[0][0]).samefile(path_adb)


def test_falls_back_to_android_sdk_root_when_android_home_missing(tmp_path: Path):
    sdk = fake_sdk(tmp_path / "sdk")
    emulator = AndroidEmulator(
        runner=MagicMock(spec=subprocess),
        environ={"PATH": "", "ANDROID_SDK_ROOT": str(sdk)},
    )

    assert emulator._adb_path() == str(
        sdk / "platform-tools" / ("adb.exe" if os.name == "nt" else "adb")
    )


def test_android_home_wins_over_android_sdk_root(tmp_path: Path):
    home = fake_sdk(tmp_path / "home")
    sdk_root = fake_sdk(tmp_path / "sdk-root")
    emulator = AndroidEmulator(
        runner=MagicMock(spec=subprocess),
        environ={"PATH": "", "ANDROID_HOME": str(home), "ANDROID_SDK_ROOT": str(sdk_root)},
    )

    assert emulator._adb_path().startswith(str(home))


def test_missing_program_error_names_program_and_locations(tmp_path: Path):
    empty_sdk = tmp_path / "empty-sdk"
    empty_sdk.mkdir()
    runner = MagicMock(spec=subprocess)
    emulator = AndroidEmulator(
        runner=runner,
        environ={"PATH": "", "ANDROID_HOME": str(empty_sdk)},
    )

    with pytest.raises(FileNotFoundError) as error:
        emulator.running_serials()

    message = str(error.value)
    assert "'adb'" in message
    assert "PATH" in message
    assert "ANDROID_HOME" in message and str(empty_sdk) in message
    assert "ANDROID_SDK_ROOT (not set)" in message
    runner.run.assert_not_called()


def test_reusing_running_emulator_does_not_need_emulator_program(tmp_path: Path):
    sdk = fake_sdk(tmp_path / "sdk", emulator=False)
    runner = MagicMock(spec=subprocess)
    runner.run.side_effect = [
        completed("List of devices attached\nemulator-5554\tdevice\n"),
        completed(),
        completed("1\n"),
    ]
    emulator = AndroidEmulator(runner=runner, environ=env_with_sdk(sdk))

    assert emulator.ensure(None, headless=False, timeout=5) == "emulator-5554"
    runner.Popen.assert_not_called()


def test_starting_avd_without_emulator_program_raises(tmp_path: Path):
    sdk = fake_sdk(tmp_path / "sdk", emulator=False)
    runner = MagicMock(spec=subprocess)
    runner.run.return_value = completed("List of devices attached\n")
    emulator = AndroidEmulator(runner=runner, environ=env_with_sdk(sdk))

    with pytest.raises(FileNotFoundError, match="'emulator'"):
        emulator.ensure("Pixel_8_API_35", headless=False, timeout=5)
