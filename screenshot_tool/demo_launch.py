"""Build demo launch commands and write their settings files."""

import json
import os
from pathlib import Path

from . import config
from .config_models import DemoSpec, LaunchSettings


def child_env(launch: LaunchSettings, demo: DemoSpec, language: str | None) -> dict[str, str] | None:
    """The environment the target app is launched with.

    The tool runs under uv, which puts ITS virtualenv first on PATH - and that
    venv has none of the recorded app's dependencies, so an app launched
    through a plain `python` would fail to import itself. Dropping it here
    saves every consumer the same three lines of shell.
    """
    if launch.inherit_env and not launch.env:
        return None
    env = dict(os.environ)
    if not launch.inherit_env:
        venv = env.pop("VIRTUAL_ENV", None)
        if venv:
            scripts = os.path.join(venv, "Scripts")
            parts = [p for p in env.get("PATH", "").split(os.pathsep) if p and p != scripts]
            env["PATH"] = os.pathsep.join(parts)
    for key, value in launch.env:
        env[key] = config.expand(value, demo, language)
    return env


def build_launch_command(
    launch: LaunchSettings,
    demo: DemoSpec,
    port: int,
    settings_file: Path | None,
    language: str | None = None,
    texts_file: Path | None = None,
) -> list[str]:
    """Substitute {demo_id}/{port}/{width}/{height} placeholders into the launch
    command and append --automation-demo-settings / --automation-demo-language /
    --automation-demo-texts when given."""
    values = {"demo_id": demo.id, "port": port, "width": demo.width, "height": demo.height}
    command = [arg.format(**values) for arg in launch.command]
    if settings_file is not None:
        command += ["--automation-demo-settings", str(settings_file)]
    if language is not None:
        command += ["--automation-demo-language", language]
    if texts_file is not None:
        command += ["--automation-demo-texts", str(texts_file)]
    return command


def write_app_settings_file(demo: DemoSpec, directory: Path) -> Path | None:
    """Write the demo's app_settings as a JSON object file.

    One file instead of one CLI argument per setting keeps the launch command
    short no matter how many settings a demo carries.

    Returns:
        The file path, or None when the demo has no app settings.
    """
    if not demo.app_settings:
        return None
    path = directory / f"demo-{demo.id}-settings.json"
    path.write_text(json.dumps(dict(demo.app_settings)), encoding="utf-8")
    return path
