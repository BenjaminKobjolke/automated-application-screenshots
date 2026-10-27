"""Fake Android SDK files and subprocess results for emulator tests."""

import os
import subprocess
from pathlib import Path


def fake_sdk(root: Path, *, adb: bool = True, emulator: bool = True) -> Path:
    suffix = ".exe" if os.name == "nt" else ""
    if adb:
        adb_path = root / "platform-tools" / f"adb{suffix}"
        adb_path.parent.mkdir(parents=True, exist_ok=True)
        adb_path.touch()
    if emulator:
        emulator_path = root / "emulator" / f"emulator{suffix}"
        emulator_path.parent.mkdir(parents=True, exist_ok=True)
        emulator_path.touch()
    return root


def env_with_sdk(sdk: Path) -> dict[str, str]:
    return {"PATH": "", "ANDROID_HOME": str(sdk)}


def completed(stdout: str = "", returncode: int = 0) -> subprocess.CompletedProcess[str]:
    return subprocess.CompletedProcess([], returncode, stdout=stdout, stderr="")
