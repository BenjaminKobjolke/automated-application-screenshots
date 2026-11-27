"""Discover, start and stop Android emulators for live Flutter sessions."""

from __future__ import annotations

import os
import subprocess
from collections.abc import Mapping
from pathlib import Path

from screenshot_tool import android_emulator_runtime as emulator_runtime
from screenshot_tool.android_emulator_lifecycle import (
    CommandRunner,
    ensure_emulator,
    stop_emulator,
)
from screenshot_tool.android_sdk import find_sdk_program
from screenshot_tool.device_screen import DeviceScreen
from screenshot_tool.emulator_logs import EmulatorLogs
from screenshot_tool.emulator_rotation import EmulatorRotation

_ADB = ("adb", "platform-tools")
_EMULATOR = ("emulator", "emulator")


class AndroidEmulator:
    """Manage an emulator while tracking whether this instance started it."""

    def __init__(
        self,
        runner: CommandRunner = subprocess,
        environ: Mapping[str, str] = os.environ,
        log_dir: Path | None = None,
    ) -> None:
        self._runner = runner
        self._environ = environ
        self._adb: str | None = None
        self._emulator: str | None = None
        self._process: subprocess.Popen[str] | None = None
        self._serial: str | None = None
        self._owns_emulator = False
        self._saved_stay_on: str | None = None
        self._has_saved_stay_on = False
        self._reversed_port: int | None = None
        self._logs = EmulatorLogs(log_dir, runner) if log_dir is not None else None

    def running_serials(self, timeout: float | None = None) -> list[str]:
        """Return online Android emulator serials reported by adb."""
        return emulator_runtime.running_serials(self._runner, self.adb_path(), timeout)

    def ensure(self, avd: str | None, headless: bool, timeout: float) -> str:
        """Reuse an online emulator or launch the requested AVD and await boot."""
        return ensure_emulator(self, avd, headless, timeout)

    def stop(self) -> None:
        """Shut down only an emulator launched by this driver."""
        stop_emulator(self)

    def device_state(self) -> str:
        """Describe adb visibility, owned process state, and available logs."""
        try:
            listed = self._serial in self.running_serials() if self._serial else False
        except (OSError, subprocess.SubprocessError) as error:
            state = f"could not query adb: {error}"
        else:
            state = (
                f"{self._serial} is still listed by adb"
                if listed
                else f"{self._serial or 'emulator'} is not listed by adb"
            )
        if self._owns_emulator and self._process is not None:
            exit_code = self._process.poll()
            state += (
                f"; emulator process exited with code {exit_code}"
                if exit_code is not None
                else "; emulator process is still running"
            )
        if self._logs is not None:
            state += f"; logs: {self._logs.emulator_path}, {self._logs.logcat_path}"
        return state

    @property
    def serial(self) -> str | None:
        """Return the serial of the emulator selected by this driver."""
        return self._serial

    def rotation(self) -> EmulatorRotation:
        """Create a rotation controller for the selected emulator."""
        if self._serial is None:
            raise RuntimeError("emulator is not started")
        return EmulatorRotation(self._runner, self.adb_path(), self._serial)

    def reverse_port(self, port: int) -> None:
        """Forward an emulator loopback port to this host through adb."""
        if self._serial is None:
            raise RuntimeError("emulator is not started")
        # adb reverse keeps loopback available in airplane mode, unlike 10.0.2.2.
        self._runner.run(
            [
                self.adb_path(),
                "-s",
                self._serial,
                "reverse",
                f"tcp:{port}",
                f"tcp:{port}",
            ],
            capture_output=True,
            check=True,
            text=True,
        )
        self._reversed_port = port

    def _remove_reverse(self) -> None:
        port = self._reversed_port
        serial = self._serial
        if port is None:
            return
        if serial is not None:
            self._runner.run(
                [
                    self.adb_path(),
                    "-s",
                    serial,
                    "reverse",
                    "--remove",
                    f"tcp:{port}",
                ],
                capture_output=True,
                check=False,
                text=True,
            )
        self._reversed_port = None

    def device_screen(self) -> DeviceScreen:
        """Create a full-device screen controller for the selected emulator."""
        if self._serial is None:
            raise RuntimeError("emulator is not started")
        return DeviceScreen(self._runner, self.adb_path(), self._serial)

    def avd_name(self, serial: str) -> str:
        """Return the AVD name associated with an emulator serial, if known."""
        return emulator_runtime.avd_name(self._runner, self.adb_path(), serial)

    def _wait_for_serial(self, timeout: float, ignore: set[str] | None = None) -> str:
        return emulator_runtime.wait_for_serial(
            self._process,
            timeout,
            self.running_serials,
            ignore,
        )

    def adb_path(self) -> str:
        """Return the resolved adb executable path."""
        if self._adb is None:
            self._adb = find_sdk_program(*_ADB, self._environ)
        return self._adb

    def _adb_path(self) -> str:
        return self.adb_path()

    def _emulator_path(self) -> str:
        if self._emulator is None:
            self._emulator = find_sdk_program(*_EMULATOR, self._environ)
        return self._emulator

    def _wait_for_boot(self, serial: str, timeout: float) -> None:
        emulator_runtime.wait_for_boot(self._runner, self.adb_path(), serial, timeout)

    def _keep_awake(self, serial: str) -> None:
        self._saved_stay_on = emulator_runtime.keep_awake(self._runner, self.adb_path(), serial)
        self._has_saved_stay_on = True

    @staticmethod
    def _kill_process_tree(pid: int) -> None:
        emulator_runtime.kill_process_tree(pid)
