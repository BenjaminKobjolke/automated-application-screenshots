"""Discover, start and stop Android emulators for live Flutter sessions."""

from __future__ import annotations

import subprocess
import time
from collections.abc import Sequence
from typing import Any, Protocol

import psutil

_BOOT_POLL_SECONDS = 1.0
_PROCESS_STOP_TIMEOUT = 3.0


class CommandRunner(Protocol):
    """Subprocess operations used by the emulator driver."""

    def run(self, args: Sequence[str], **kwargs: Any) -> subprocess.CompletedProcess[str]: ...

    def Popen(self, args: Sequence[str], **kwargs: Any) -> subprocess.Popen[str]: ...


class AndroidEmulator:
    """Manage an emulator while tracking whether this instance started it."""

    def __init__(self, runner: CommandRunner = subprocess) -> None:
        self._runner = runner
        self._process: subprocess.Popen[str] | None = None
        self._serial: str | None = None
        self._owns_emulator = False

    def running_serials(self) -> list[str]:
        """Return online Android emulator serials reported by adb."""
        result = self._runner.run(["adb", "devices"], capture_output=True, check=True, text=True)
        serials: list[str] = []
        for line in result.stdout.splitlines()[1:]:
            columns = line.split()
            if len(columns) >= 2 and columns[0].startswith("emulator-") and columns[1] == "device":
                serials.append(columns[0])
        return serials

    def ensure(self, avd: str | None, headless: bool, timeout: float) -> str:
        """Reuse an online emulator or launch the requested AVD and await boot."""
        existing = self.running_serials()
        if existing:
            self._serial = existing[0]
        else:
            if not avd:
                raise ValueError("live.avd is required when no Android emulator is running")
            command = ["emulator", "-avd", avd]
            if headless:
                command.append("-no-window")
            command.append("-no-snapshot-save")
            self._process = self._runner.Popen(
                command,
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
            )
            self._owns_emulator = True
            self._serial = self._wait_for_serial(timeout)

        self._wait_for_boot(self._serial, timeout)
        return self._serial

    def stop(self) -> None:
        """Shut down only an emulator launched by this driver."""
        if not self._owns_emulator:
            return
        serial = self._serial
        if serial:
            self._runner.run(
                ["adb", "-s", serial, "emu", "kill"],
                capture_output=True,
                check=False,
                text=True,
            )
        if self._process is not None and self._process.poll() is None:
            self._kill_process_tree(self._process.pid)
        self._process = None
        self._serial = None
        self._owns_emulator = False

    def _wait_for_serial(self, timeout: float) -> str:
        deadline = time.monotonic() + timeout
        while time.monotonic() < deadline:
            if self._process is not None and self._process.poll() is not None:
                raise RuntimeError("Android emulator exited before connecting to adb")
            serials = self.running_serials()
            if serials:
                return serials[0]
            time.sleep(min(_BOOT_POLL_SECONDS, max(0, deadline - time.monotonic())))
        raise TimeoutError("Android emulator did not connect to adb before timeout")

    def _wait_for_boot(self, serial: str, timeout: float) -> None:
        deadline = time.monotonic() + timeout
        remaining = deadline - time.monotonic()
        if remaining <= 0:
            raise TimeoutError(f"Android emulator {serial} did not become available before timeout")
        try:
            self._runner.run(
                ["adb", "-s", serial, "wait-for-device"],
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
                ["adb", "-s", serial, "shell", "getprop", "sys.boot_completed"],
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
            try:
                process.kill()
            except (psutil.NoSuchProcess, psutil.AccessDenied):
                pass
        psutil.wait_procs([*children, root], timeout=_PROCESS_STOP_TIMEOUT)
