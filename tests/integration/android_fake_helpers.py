"""Helpers for running Android emulator integration cases without an SDK."""

from __future__ import annotations

import os
import sys
from pathlib import Path

import pytest

FAKE_SDK = Path(__file__).parents[1] / "fixtures" / "fake_android_sdk.py"


def install_fake_android(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    """Install adb/emulator shims and return their isolated state folder."""
    sdk_bin = tmp_path / "sdk-bin"
    sdk_bin.mkdir()
    state = tmp_path / "android-state"
    state.mkdir()
    for name in ("adb", "emulator"):
        if os.name == "nt":
            shim = sdk_bin / f"{name}.bat"
            shim.write_text(
                f'@"{sys.executable}" "{FAKE_SDK}" {name} %*\n', encoding="utf-8"
            )
        else:
            shim = sdk_bin / name
            shim.write_text(
                f'#!/bin/sh\nexec "{sys.executable}" "{FAKE_SDK}" {name} "$@"\n',
                encoding="utf-8",
            )
            shim.chmod(0o755)

    monkeypatch.setenv("PATH", str(sdk_bin) + os.pathsep + os.environ.get("PATH", ""))
    monkeypatch.delenv("ANDROID_HOME", raising=False)
    monkeypatch.delenv("ANDROID_SDK_ROOT", raising=False)
    monkeypatch.setenv("FAKE_ANDROID_STATE", str(state))
    return state
