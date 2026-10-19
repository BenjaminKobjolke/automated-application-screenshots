"""Focused tests for Android emulator discovery and ownership."""

import os
import subprocess
from pathlib import Path
from unittest.mock import MagicMock

import pytest

from screenshot_tool.android_emulator import AndroidEmulator


def fake_sdk(root: Path, *, adb: bool = True, emulator: bool = True) -> Path:
    suffix = ".exe" if os.name == "nt" else ""
    if adb:
        adb_path = root / "platform-tools" / f"adb{suffix}"
        adb_path.parent.mkdir(parents=True, exist_ok=True)
        adb_path.touch()
    if emulator:
        emulator_path = root / "emulator" / f"emulator{suffix}"
        emulator_path.parent.mkdir(parents=True, exist_ok=True)
        emulator_path.touch()
    return root


def env_with_sdk(sdk: Path) -> dict[str, str]:
    return {"PATH": "", "ANDROID_HOME": str(sdk)}


def completed(stdout: str = "", returncode: int = 0) -> subprocess.CompletedProcess[str]:
    return subprocess.CompletedProcess([], returncode, stdout=stdout, stderr="")


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
