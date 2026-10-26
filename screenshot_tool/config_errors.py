"""Shared error reporting for configuration parsing."""

from pathlib import Path
from typing import NoReturn


def _fail(config_path: Path, message: str) -> NoReturn:
    raise SystemExit(f"ERROR: Config {config_path}: {message}")
