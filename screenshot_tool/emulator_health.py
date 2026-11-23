"""Detect reused emulators too slow for Flutter's install and uninstall timeouts."""

from __future__ import annotations

import subprocess
import time
from collections.abc import Callable
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from screenshot_tool.android_emulator import CommandRunner

SLOW_PACKAGE_MANAGER_SECONDS = 10.0
_DISCONNECT_TIMEOUT_SECONDS = 30.0
_DISCONNECT_POLL_SECONDS = 1.0


def package_manager_seconds(runner: CommandRunner, adb: str, serial: str) -> float:
    """Time a cheap package-manager query, treating an ADB timeout as unhealthy."""
    started = time.monotonic()
    try:
        runner.run(
            [adb, "-s", serial, "shell", "pm", "path", "android"],
            capture_output=True,
            check=False,
            text=True,
            timeout=SLOW_PACKAGE_MANAGER_SECONDS,
        )
    except subprocess.TimeoutExpired:
        return max(time.monotonic() - started, SLOW_PACKAGE_MANAGER_SECONDS)
    return time.monotonic() - started


def wait_until_disconnected(
    list_serials: Callable[[float], list[str]], serial: str, timeout: float
) -> None:
    """Wait until adb no longer lists the serial or the bounded wait expires."""
    deadline = time.monotonic() + timeout
    while True:
        remaining = deadline - time.monotonic()
        if remaining <= 0:
            raise TimeoutError(f"Android emulator {serial} stayed connected after shutdown")
        try:
            serials = list_serials(remaining)
        except subprocess.TimeoutExpired as error:
            raise TimeoutError(
                f"Android emulator {serial} stayed connected after shutdown"
            ) from error
        if serial not in serials:
            return
        remaining = deadline - time.monotonic()
        if remaining <= 0:
            raise TimeoutError(f"Android emulator {serial} stayed connected after shutdown")
        time.sleep(min(_DISCONNECT_POLL_SECONDS, remaining))


def restart_degraded(
    runner: CommandRunner,
    adb: str,
    serial: str,
    avd: str | None,
    seconds: float,
    resolve_avd: Callable[[str], str],
    list_serials: Callable[[float], list[str]],
) -> str:
    """Stop a slow reused emulator and return the AVD name needed to relaunch it."""
    avd_name = avd or resolve_avd(serial)
    details = f'"pm path android" took {seconds:.1f} s (limit {SLOW_PACKAGE_MANAGER_SECONDS:g} s)'
    if not avd_name:
        raise RuntimeError(
            f"Android emulator {serial} is too slow: {details}, and its AVD name is unknown, "
            "so it cannot be restarted. "
            "Close it, set live.avd, and run --live-start again."
        )
    runner.run(
        [adb, "-s", serial, "emu", "kill"],
        capture_output=True,
        check=False,
        text=True,
    )
    try:
        wait_until_disconnected(list_serials, serial, _DISCONNECT_TIMEOUT_SECONDS)
    except TimeoutError as error:
        raise RuntimeError(
            f"Android emulator {serial} ({avd_name}) is too slow: {details}, and it did "
            "not shut down for a restart. Close the emulator (adb -s "
            f"{serial} emu kill, or its window) and run --live-start again."
        ) from error
    return avd_name
