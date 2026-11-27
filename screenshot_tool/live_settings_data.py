"""JSON conversion for settings passed to detached live sessions."""

from __future__ import annotations

import json
from pathlib import Path

from .live_config import LiveSettings, LiveTarget


def settings_to_data(settings: LiveSettings) -> dict[str, object]:
    """Return live settings in the JSON-compatible shape used by detached sessions."""
    return {
        "target": settings.target.value,
        "port": settings.port,
        "avd": settings.avd,
        "devices": settings.devices,
        "headless": settings.headless,
        "flutter": list(settings.flutter),
        "run_args": list(settings.run_args),
        "project_dir": str(settings.project_dir),
        "app_settings": settings.app_settings,
        "start_timeout": settings.start_timeout,
    }


def settings_from_data(value: str) -> LiveSettings:
    """Build live settings from the JSON line sent to a detached server."""
    data = json.loads(value)
    if not isinstance(data, dict):
        raise ValueError("invalid detached live settings")
    return LiveSettings(
        target=LiveTarget(data["target"]),
        port=data["port"],
        avd=data["avd"],
        devices=data["devices"],
        headless=data["headless"],
        flutter=tuple(data["flutter"]),
        run_args=tuple(data["run_args"]),
        project_dir=Path(data["project_dir"]),
        app_settings=data["app_settings"],
        start_timeout=data["start_timeout"],
    )
