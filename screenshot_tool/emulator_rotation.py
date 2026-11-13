"""Lock Android emulator orientation for one screenshot and restore it afterward."""

from __future__ import annotations

import re
import subprocess
import time
from collections.abc import Iterator, Sequence
from contextlib import contextmanager
from typing import Any, Protocol

from screenshot_tool.app_logger import AppLogger

_POLL_SECONDS = 0.25
_SETTLE_SECONDS = 1.0
_SIZE_PATTERN = re.compile(r"(?:Override|Physical) size:\s*(\d+)x(\d+)")
_OVERRIDE_SIZE_PATTERN = re.compile(r"Override size:\s*(\d+)x(\d+)")
_ROTATION_PATTERN = re.compile(r"mOverrideDisplayInfo[^\n]*?rotation\s+(\d+)")


class CommandRunner(Protocol):
    """Subprocess operation required by the rotation controller."""

    def run(self, args: Sequence[str], **kwargs: Any) -> subprocess.CompletedProcess[str]: ...


def parse_wm_size(output: str) -> tuple[int, int]:
    """Return the active override size, or the physical display size."""
    override = _OVERRIDE_SIZE_PATTERN.search(output)
    match = override or _SIZE_PATTERN.search(output)
    if match is None:
        raise ValueError("Could not parse display size from adb wm size output")
    return int(match.group(1)), int(match.group(2))


def parse_display_rotation(output: str) -> int:
    """Return the rotation reported by dumpsys display's override info."""
    match = _ROTATION_PATTERN.search(output)
    if match is None:
        raise ValueError("Could not parse rotation from dumpsys display output")
    return int(match.group(1))


class EmulatorRotation:
    """Temporarily rotate one emulator while preserving its prior settings."""

    def __init__(self, runner: CommandRunner, adb: str, serial: str) -> None:
        self._runner = runner
        self._adb = adb
        self._serial = serial

    @contextmanager
    def locked(self, landscape: bool, timeout: float) -> Iterator[None]:
        """Lock orientation for a capture and restore the original settings."""
        accelerometer_rotation = self._get_setting("accelerometer_rotation") or "1"
        user_rotation = self._get_setting("user_rotation") or "0"
        if accelerometer_rotation == "null":
            accelerometer_rotation = "1"
        if user_rotation == "null":
            user_rotation = "0"

        original_rotation = self._display_rotation()
        width, height = parse_wm_size(self._run("shell", "wm", "size"))
        natural_landscape = width > height
        orientation = "landscape" if landscape else "portrait"
        target_rotation = 0 if landscape == natural_landscape else 1

        try:
            self._put_setting("accelerometer_rotation", "0")
            self._put_setting("user_rotation", str(target_rotation))
            self._wait_for_rotation(target_rotation, timeout, orientation)
            # Flutter needs a frame to re-layout after Android reports the new display rotation.
            time.sleep(_SETTLE_SECONDS)
            yield
        finally:
            self._put_setting("accelerometer_rotation", accelerometer_rotation)
            self._put_setting("user_rotation", user_rotation)
            try:
                self._wait_for_rotation(original_rotation, timeout, "original orientation")
            except TimeoutError as error:
                AppLogger.warning(str(error))

    def _get_setting(self, setting: str) -> str:
        return self._run("shell", "settings", "get", "system", setting).strip()

    def _put_setting(self, setting: str, value: str) -> None:
        self._run("shell", "settings", "put", "system", setting, value)

    def _display_rotation(self) -> int:
        return parse_display_rotation(self._run("shell", "dumpsys", "display"))

    def _wait_for_rotation(self, rotation: int, timeout: float, orientation: str) -> None:
        deadline = time.monotonic() + timeout
        while time.monotonic() < deadline:
            try:
                if self._display_rotation() == rotation:
                    return
            except ValueError:
                # A booting or incompatible system image may not expose this line yet.
                pass
            time.sleep(min(_POLL_SECONDS, max(0, deadline - time.monotonic())))
        raise TimeoutError(
            f"Android emulator {self._serial} did not rotate to {orientation} before timeout"
        )

    def _run(self, *arguments: str) -> str:
        result = self._runner.run(
            [self._adb, "-s", self._serial, *arguments],
            capture_output=True,
            check=True,
            text=True,
        )
        return result.stdout
