"""Coordinate emulator startup and ownership-aware shutdown."""

from __future__ import annotations

import subprocess
from collections.abc import Sequence
from typing import Any, Protocol

from screenshot_tool import android_emulator_runtime as emulator_runtime
from screenshot_tool.emulator_health import (
    SLOW_PACKAGE_MANAGER_SECONDS,
    package_manager_seconds,
    restart_degraded,
)

_STAY_ON_SETTING = "stay_on_while_plugged_in"


class CommandRunner(Protocol):
    """Subprocess operations used by the emulator driver."""

    def run(self, args: Sequence[str], **kwargs: Any) -> subprocess.CompletedProcess[str]: ...

    def Popen(self, args: Sequence[str], **kwargs: Any) -> subprocess.Popen[str]: ...


class EmulatorLifecycleHost(Protocol):
    """Driver state and operations needed by emulator lifecycle coordination."""

    _runner: CommandRunner
    _process: subprocess.Popen[str] | None
    _serial: str | None
    _owns_emulator: bool
    _saved_stay_on: str | None
    _has_saved_stay_on: bool
    _logs: Any

    def running_serials(self) -> list[str]: ...

    def avd_name(self, serial: str) -> str: ...

    def adb_path(self) -> str: ...

    def _emulator_path(self) -> str: ...

    def _wait_for_serial(self, timeout: float, ignore: set[str] | None = None) -> str: ...

    def _wait_for_boot(self, serial: str, timeout: float) -> None: ...

    def _keep_awake(self, serial: str) -> None: ...

    def _remove_reverse(self) -> None: ...


def ensure_emulator(
    host: EmulatorLifecycleHost, avd: str | None, headless: bool, timeout: float
) -> str:
    """Reuse an online emulator or launch the requested AVD and await boot."""
    existing = host.running_serials()
    owned_serial = host._serial
    if avd is None:
        if existing:
            host._serial = existing[0]
        else:
            raise ValueError("live.avd is required when no Android emulator is running")
    else:
        host._serial = next((serial for serial in existing if host.avd_name(serial) == avd), None)

    _stop_unlisted_owned_emulator(host, existing, owned_serial)

    if host._serial is not None:
        serial = host._serial
        host._wait_for_boot(serial, timeout)
        seconds = package_manager_seconds(host._runner, host.adb_path(), serial)
        if seconds >= SLOW_PACKAGE_MANAGER_SECONDS:
            avd = restart_degraded(
                host._runner,
                host.adb_path(),
                serial,
                avd,
                seconds,
                host.avd_name,
                host.running_serials,
            )
            host._serial = None
            existing.remove(serial)
        else:
            host._keep_awake(serial)
            if host._logs is not None:
                host._logs.start_logcat(host.adb_path(), serial)
            return serial

    if host._serial is None:
        if not avd:
            raise ValueError("live.avd is required when no Android emulator is running")
        command = [host._emulator_path(), "-avd", avd]
        if headless:
            command.append("-no-window")
        command.append("-no-snapshot-save")
        # A pending crash report can block startup on a hidden consent dialog.
        command += ["-crash-report-mode", "disabled"]
        output = host._logs.open_emulator_output() if host._logs is not None else subprocess.DEVNULL
        host._process = host._runner.Popen(command, stdout=output, stderr=output)
        host._owns_emulator = True
        host._serial = host._wait_for_serial(timeout, ignore=set(existing))

    host._wait_for_boot(host._serial, timeout)
    host._keep_awake(host._serial)
    if host._logs is not None:
        host._logs.start_logcat(host.adb_path(), host._serial)
    return host._serial


def _stop_unlisted_owned_emulator(
    host: EmulatorLifecycleHost, existing: list[str], owned_serial: str | None
) -> None:
    """Clear a stale owned process before starting a replacement AVD."""
    process = host._process
    if host._serial is not None:
        return
    if not host._owns_emulator or process is None:
        return
    if owned_serial is None or owned_serial in existing:
        return
    if process.poll() is not None:
        return

    # ADB can lose a still-running owned process; clear it before launching its replacement.
    emulator_runtime.kill_process_tree(process.pid)
    host._process = None
    host._owns_emulator = False


def stop_emulator(host: EmulatorLifecycleHost) -> None:
    """Shut down only a driver-owned emulator and restore reused-device settings."""
    try:
        host._remove_reverse()
        if not host._owns_emulator:
            if host._has_saved_stay_on and host._serial is not None:
                restore_command = (
                    ["settings", "put", "global", _STAY_ON_SETTING, host._saved_stay_on]
                    if host._saved_stay_on is not None
                    else ["settings", "delete", "global", _STAY_ON_SETTING]
                )
                host._runner.run(
                    [host.adb_path(), "-s", host._serial, "shell", *restore_command],
                    capture_output=True,
                    check=False,
                    text=True,
                )
            host._saved_stay_on = None
            host._has_saved_stay_on = False
            return
        host._saved_stay_on = None
        host._has_saved_stay_on = False
        serial = host._serial
        if serial:
            host._runner.run(
                [host.adb_path(), "-s", serial, "emu", "kill"],
                capture_output=True,
                check=False,
                text=True,
            )
        if host._process is not None and host._process.poll() is None:
            emulator_runtime.kill_process_tree(host._process.pid)
        host._process = None
        host._serial = None
        host._owns_emulator = False
    finally:
        if host._logs is not None:
            host._logs.close()
