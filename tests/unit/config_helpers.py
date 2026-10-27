"""Shared helpers for writing configuration test data."""

import json
from pathlib import Path


def write_config(tmp_path: Path, data: dict[str, object]) -> Path:
    path = tmp_path / "app.json"
    path.write_text(json.dumps(data), encoding="utf-8")
    return path
