"""Discover, start and stop Android emulators for live Flutter sessions."""

from __future__ import annotations

import os
import shutil
import subprocess
import time
from collections.abc import Mapping, Sequence
from contextlib import suppress
from pathlib import Path
from typing import Any, Protocol

import psutil

from screenshot_tool.emulator_rotation import EmulatorRotation

_BOOT_POLL_SECONDS = 1.0
_PROCESS_STOP_TIMEOUT = 3.0
_SDK_ENV_VARS = ("ANDROID_HOME", "ANDROID_SDK_ROOT")
_ADB = ("adb", "platform-tools")
_EMULATOR = ("emulator", "emulator")


def find_sdk_program(name: str, sdk_subdir: str, environ: Mapping[str, str]) -> str:
    """Find an Android SDK program on PATH or in either configured SDK root."""
    path_match = shutil.which(name, path=environ.get("PATH", ""))
    if path_match:
        return path_match

    executable = f"{name}.exe" if os.name == "nt" else name
    locations: list[str] = ["PATH"]
    for variable in _SDK_ENV_VARS:
        root = environ.get(variable, "")
        if root:
            candidate = Path(root) / sdk_subdir / executable
            locations.append(f"{variable} ({root})")
            if candidate.is_file():
                return str(candidate)
        else:
            locations.append(f"{variable} (not set)")

    raise FileNotFoundError(
        f"Android SDK program '{name}' not found. Looked on {', in '.join(locations)}."
    )


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

    def running_serials(self) -> list[str]:
        """Return online Android emulator serials reported by adb."""
        result = self._runner.run(
            [self._adb_path(), "devices"], capture_output=True, check=True, text=True
        )
        serials: list[str] = []
        for line in result.stdout.splitlines()[1:]:
            columns = line.split()
            is_online_emulator = (
                len(columns) >= 2 and columns[0].startswith("emulator-") and columns[1] == "device"
            )
            if is_online_emulator:
                serials.append(columns[0])
        return serials

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
        return self._serial

    def stop(self) -> None:
        """Shut down only an emulator launched by this driver."""
        if not self._owns_emulator:
            return
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

    def avd_name(self, serial: str) -> str:
        """Return the AVD name associated with an emulator serial, if known."""
        result = self._runner.run(
            [self.adb_path(), "-s", serial, "emu", "avd", "name"],
            capture_output=True,
            check=False,
            text=True,
        )
        return next((line.strip() for line in result.stdout.splitlines() if line.strip()), "")

    def _wait_for_serial(self, timeout: float, ignore: set[str] | None = None) -> str:
        deadline = time.monotonic() + timeout
        ignored = ignore or set()
        while time.monotonic() < deadline:
            if self._process is not None and self._process.poll() is not None:
                raise RuntimeError("Android emulator exited before connecting to adb")
            serials = self.running_serials()
            available = [serial for serial in serials if serial not in ignored]
            if available:
                return available[0]
            time.sleep(min(_BOOT_POLL_SECONDS, max(0, deadline - time.monotonic())))
        raise TimeoutError("Android emulator did not connect to adb before timeout")

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
        deadline = time.monotonic() + timeout
        remaining = deadline - time.monotonic()
        if remaining <= 0:
            raise TimeoutError(f"Android emulator {serial} did not become available before timeout")
        try:
            self._runner.run(
                [self._adb_path(), "-s", serial, "wait-for-device"],
                capture_output=True,
                check=True,
                text=True,
                timeout=remaining,
            )
        except subprocess.TimeoutExpired as error:
            raise TimeoutError(
                f"Android emulator {serial} did not become available before timeout"
            ) from error
        while time.monotonic() < deadline:
            result = self._runner.run(
                [self._adb_path(), "-s", serial, "shell", "getprop", "sys.boot_completed"],
                capture_output=True,
                check=True,
                text=True,
            )
            if result.stdout.strip() == "1":
                return
            time.sleep(min(_BOOT_POLL_SECONDS, max(0, deadline - time.monotonic())))
        raise TimeoutError(f"Android emulator {serial} did not finish booting before timeout")

    @staticmethod
    def _kill_process_tree(pid: int) -> None:
        try:
            root = psutil.Process(pid)
            children = root.children(recursive=True)
        except psutil.NoSuchProcess:
            return
        for process in [*children, root]:
            with suppress(psutil.NoSuchProcess, psutil.AccessDenied):
                process.kill()
        psutil.wait_procs([*children, root], timeout=_PROCESS_STOP_TIMEOUT)
