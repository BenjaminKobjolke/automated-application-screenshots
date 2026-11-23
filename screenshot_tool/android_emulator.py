"""Discover, start and stop Android emulators for live Flutter sessions."""

from __future__ import annotations

import os
import subprocess
from collections.abc import Mapping, Sequence
from typing import Any, Protocol

from screenshot_tool import android_emulator_runtime as emulator_runtime
from screenshot_tool.android_sdk import find_sdk_program
from screenshot_tool.device_screen import DeviceScreen
from screenshot_tool.emulator_health import (
    SLOW_PACKAGE_MANAGER_SECONDS,
    package_manager_seconds,
    restart_degraded,
)
from screenshot_tool.emulator_rotation import EmulatorRotation

_ADB = ("adb", "platform-tools")
_EMULATOR = ("emulator", "emulator")
_STAY_ON_SETTING = "stay_on_while_plugged_in"


class CommandRunner(Protocol):
    """Subprocess operations used by the emulator driver."""

    def run(self, args: Sequence[str], **kwargs: Any) -> subprocess.CompletedProcess[str]: ...

    def Popen(self, args: Sequence[str], **kwargs: Any) -> subprocess.Popen[str]: ...


class AndroidEmulator:
    """Manage an emulator while tracking whether this instance started it."""

    def __init__(
        self,
        runner: CommandRunner = subprocess,
        environ: Mapping[str, str] = os.environ,
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

    def running_serials(self, timeout: float | None = None) -> list[str]:
        """Return online Android emulator serials reported by adb."""
        return emulator_runtime.running_serials(self._runner, self.adb_path(), timeout)

    def ensure(self, avd: str | None, headless: bool, timeout: float) -> str:
        """Reuse an online emulator or launch the requested AVD and await boot."""
        existing = self.running_serials()
        if avd is None:
            if existing:
                self._serial = existing[0]
            else:
                raise ValueError("live.avd is required when no Android emulator is running")
        else:
            self._serial = next(
                (serial for serial in existing if self.avd_name(serial) == avd), None
            )

        if self._serial is not None:
            serial = self._serial
            self._wait_for_boot(serial, timeout)
            seconds = package_manager_seconds(self._runner, self.adb_path(), serial)
            if seconds >= SLOW_PACKAGE_MANAGER_SECONDS:
                avd = restart_degraded(
                    self._runner,
                    self.adb_path(),
                    serial,
                    avd,
                    seconds,
                    self.avd_name,
                    self.running_serials,
                )
                self._serial = None
                existing.remove(serial)
            else:
                self._keep_awake(serial)
                return serial

        if self._serial is None:
            if not avd:
                raise ValueError("live.avd is required when no Android emulator is running")
            command = [self._emulator_path(), "-avd", avd]
            if headless:
                command.append("-no-window")
            command.append("-no-snapshot-save")
            # A pending crash report can block startup on a hidden consent dialog.
            command += ["-crash-report-mode", "disabled"]
            self._process = self._runner.Popen(
                command,
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
            )
            self._owns_emulator = True
            self._serial = self._wait_for_serial(timeout, ignore=set(existing))

        self._wait_for_boot(self._serial, timeout)
        self._keep_awake(self._serial)
        return self._serial

    def stop(self) -> None:
        """Shut down only an emulator launched by this driver."""
        if not self._owns_emulator:
            if self._has_saved_stay_on and self._serial is not None:
                restore_command = (
                    ["settings", "put", "global", _STAY_ON_SETTING, self._saved_stay_on]
                    if self._saved_stay_on is not None
                    else ["settings", "delete", "global", _STAY_ON_SETTING]
                )
                self._runner.run(
                    [
                        self._adb_path(),
                        "-s",
                        self._serial,
                        "shell",
                        *restore_command,
                    ],
                    capture_output=True,
                    check=False,
                    text=True,
                )
            self._saved_stay_on = None
            self._has_saved_stay_on = False
            return
        self._saved_stay_on = None
        self._has_saved_stay_on = False
        serial = self._serial
        if serial:
            self._runner.run(
                [self._adb_path(), "-s", serial, "emu", "kill"],
                capture_output=True,
                check=False,
                text=True,
            )
        if self._process is not None and self._process.poll() is None:
            self._kill_process_tree(self._process.pid)
        self._process = None
        self._serial = None
        self._owns_emulator = False

    @property
    def serial(self) -> str | None:
        """Return the serial of the emulator selected by this driver."""
        return self._serial

    def rotation(self) -> EmulatorRotation:
        """Create a rotation controller for the selected emulator."""
        if self._serial is None:
            raise RuntimeError("emulator is not started")
        return EmulatorRotation(self._runner, self.adb_path(), self._serial)

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
