"""Pause FancyZones during demos so its remembered zones cannot resize new windows.

The workstation logs confirmed FancyZones reapplies a saved zone when an app starts.
It can also resize the window again a few seconds later, racing the app's demo setup.
"""

import subprocess
from contextlib import contextmanager
from typing import Iterator

import psutil

from .app_logger import AppLogger

PROCESS_NAME = "PowerToys.FancyZones.exe"
STOP_TIMEOUT_S = 5.0


def _running() -> list[psutil.Process]:
    """Return currently running FancyZones processes."""
    return [
        process
        for process in psutil.process_iter(["name"])
        if (process.info.get("name") or "").casefold() == PROCESS_NAME.casefold()
    ]


def _stop() -> list[list[str]]:
    """Stop each accessible instance and retain its launch command."""
    commands = []
    for process in _running():
        try:
            command = process.cmdline()
            process.terminate()
            process.wait(timeout=STOP_TIMEOUT_S)
            commands.append(command)
            AppLogger.info(f"Stopped {PROCESS_NAME}.")
        except (psutil.AccessDenied, psutil.NoSuchProcess, psutil.TimeoutExpired) as error:
            AppLogger.warning(f"Could not stop {PROCESS_NAME}: {error}")
    return commands


def _restart(commands: list[list[str]]) -> None:
    """Restart stopped instances unless FancyZones has already returned."""
    if not commands or _running():
        return
    flags = subprocess.DETACHED_PROCESS | subprocess.CREATE_NEW_PROCESS_GROUP
    for command in commands:
        try:
            subprocess.Popen(command, creationflags=flags)
            AppLogger.info(f"Restarted {PROCESS_NAME}.")
        except OSError as error:
            AppLogger.error(f"Could not restart {command!r}: {error}")


@contextmanager
def paused(enabled: bool = True) -> Iterator[None]:
    """Pause FancyZones for a demo and restore only instances stopped here."""
    commands = _stop() if enabled else []
    try:
        yield
    finally:
        _restart(commands)
