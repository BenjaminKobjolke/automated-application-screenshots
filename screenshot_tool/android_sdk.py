"""Resolve Android SDK executables from PATH and configured SDK roots."""

from __future__ import annotations

import os
import shutil
from collections.abc import Mapping
from pathlib import Path

_SDK_ENV_VARS = ("ANDROID_HOME", "ANDROID_SDK_ROOT")


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
