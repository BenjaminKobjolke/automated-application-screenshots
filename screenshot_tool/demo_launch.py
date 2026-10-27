"""Build demo launch commands and write their settings files."""

import json
from pathlib import Path

from .config_models import DemoSpec, LaunchSettings


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
