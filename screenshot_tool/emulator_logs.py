"""Capture the host and guest logs for one detached Android emulator session."""

from __future__ import annotations

import subprocess
from collections.abc import Sequence
from pathlib import Path
from typing import IO, Protocol


class ProcessRunner(Protocol):
    """Process operations needed to record adb output."""

    def Popen(self, args: Sequence[str], **kwargs: object) -> subprocess.Popen[str]: ...


class EmulatorLogs:
    """Own emulator output and a streaming adb logcat process."""

    def __init__(self, directory: Path, runner: ProcessRunner) -> None:
        self.directory = directory
        self._runner = runner
        self._emulator_file: IO[bytes] | None = None
        self._logcat_file: IO[bytes] | None = None
        self._logcat_process: subprocess.Popen[str] | None = None

    @property
    def emulator_path(self) -> Path:
        return self.directory / "emulator.log"

    @property
    def logcat_path(self) -> Path:
        return self.directory / "logcat.txt"

    def open_emulator_output(self) -> IO[bytes]:
        """Open the emulator's host-side output file for its launch."""
        self.directory.mkdir(parents=True, exist_ok=True)
        if self._emulator_file is None or self._emulator_file.closed:
            self._emulator_file = self.emulator_path.open("ab")
        return self._emulator_file

    def start_logcat(self, adb: str, serial: str) -> None:
        """Start a fresh device log stream, replacing any previous recorder."""
        self.stop_logcat()
        self.directory.mkdir(parents=True, exist_ok=True)
        self._logcat_file = self.logcat_path.open("ab")
        try:
            self._logcat_process = self._runner.Popen(
                [adb, "-s", serial, "logcat", "-v", "threadtime", "-T", "1"],
                stdout=self._logcat_file,
                stderr=subprocess.STDOUT,
            )
        except Exception:
            self._logcat_file.close()
            self._logcat_file = None
            raise

    def stop_logcat(self) -> None:
        """Stop the recorder and close its output file."""
        process = self._logcat_process
        self._logcat_process = None
        if process is not None and process.poll() is None:
            process.terminate()
            try:
                process.wait(timeout=5)
            except subprocess.TimeoutExpired:
                process.kill()
                process.wait(timeout=5)
        if self._logcat_file is not None:
            self._logcat_file.close()
            self._logcat_file = None

    def close(self) -> None:
        """Stop the guest log and close host output."""
        self.stop_logcat()
        if self._emulator_file is not None:
            self._emulator_file.close()
            self._emulator_file = None
