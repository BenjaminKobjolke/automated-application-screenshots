"""Low-level ADB and process operations for Android emulator sessions."""

from __future__ import annotations

import subprocess
import time
from collections.abc import Callable
from contextlib import suppress
from typing import Any, Protocol

import psutil

_BOOT_POLL_SECONDS = 1.0
_PROCESS_STOP_TIMEOUT = 3.0
_STAY_ON_SETTING = "stay_on_while_plugged_in"
_WAKE_COMMANDS = (
    ("svc", "power", "stayon", "true"),
    ("input", "keyevent", "KEYCODE_WAKEUP"),
    ("wm", "dismiss-keyguard"),
)


class CommandRunner(Protocol):
    """Subprocess operations used by emulator runtime helpers."""

    def run(self, args: list[str], **kwargs: Any) -> subprocess.CompletedProcess[str]: ...


def running_serials(runner: CommandRunner, adb: str, timeout: float | None = None) -> list[str]:
    """Return online Android emulator serials reported by adb."""
    options: dict[str, object] = {"capture_output": True, "check": True, "text": True}
    if timeout is not None:
        options["timeout"] = timeout
    result = runner.run([adb, "devices"], **options)
    serials: list[str] = []
    for line in result.stdout.splitlines()[1:]:
        columns = line.split()
        is_online_emulator = (
            len(columns) >= 2 and columns[0].startswith("emulator-") and columns[1] == "device"
        )
        if is_online_emulator:
            serials.append(columns[0])
    return serials


def avd_name(runner: CommandRunner, adb: str, serial: str) -> str:
    """Return the AVD name associated with an emulator serial, if known."""
    result = runner.run(
        [adb, "-s", serial, "emu", "avd", "name"],
        capture_output=True,
        check=False,
        text=True,
    )
    return next((line.strip() for line in result.stdout.splitlines() if line.strip()), "")


def wait_for_serial(
    process: subprocess.Popen[str] | None,
    timeout: float,
    list_serials: Callable[[], list[str]],
    ignore: set[str] | None = None,
) -> str:
    """Wait until a newly launched emulator appears in adb."""
    deadline = time.monotonic() + timeout
    ignored = ignore or set()
    while time.monotonic() < deadline:
        if process is not None and process.poll() is not None:
            raise RuntimeError("Android emulator exited before connecting to adb")
        available = [serial for serial in list_serials() if serial not in ignored]
        if available:
            return available[0]
        time.sleep(min(_BOOT_POLL_SECONDS, max(0, deadline - time.monotonic())))
    raise TimeoutError("Android emulator did not connect to adb before timeout")


def wait_for_boot(runner: CommandRunner, adb: str, serial: str, timeout: float) -> None:
    """Wait for adb connectivity and the Android boot-completed property."""
    deadline = time.monotonic() + timeout
    remaining = deadline - time.monotonic()
    if remaining <= 0:
        raise TimeoutError(f"Android emulator {serial} did not become available before timeout")
    try:
        runner.run(
            [adb, "-s", serial, "wait-for-device"],
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
        result = runner.run(
            [adb, "-s", serial, "shell", "getprop", "sys.boot_completed"],
            capture_output=True,
            check=True,
            text=True,
        )
        if result.stdout.strip() == "1":
            return
        time.sleep(min(_BOOT_POLL_SECONDS, max(0, deadline - time.monotonic())))
    raise TimeoutError(f"Android emulator {serial} did not finish booting before timeout")


def keep_awake(runner: CommandRunner, adb: str, serial: str) -> str | None:
    """Keep the emulator awake and return its previous stay-on setting."""
    result = runner.run(
        [adb, "-s", serial, "shell", "settings", "get", "global", _STAY_ON_SETTING],
        capture_output=True,
        check=True,
        text=True,
    )
    saved_stay_on = result.stdout.strip()
    for command in _WAKE_COMMANDS:
        runner.run(
            [adb, "-s", serial, "shell", *command],
            capture_output=True,
            check=True,
            text=True,
        )
    return None if saved_stay_on == "null" else saved_stay_on


def kill_process_tree(pid: int) -> None:
    """Kill an emulator process and its descendants if they still exist."""
    try:
        root = psutil.Process(pid)
        children = root.children(recursive=True)
    except psutil.NoSuchProcess:
        return
    for process in [*children, root]:
        with suppress(psutil.NoSuchProcess, psutil.AccessDenied):
            process.kill()
    psutil.wait_procs([*children, root], timeout=_PROCESS_STOP_TIMEOUT)
