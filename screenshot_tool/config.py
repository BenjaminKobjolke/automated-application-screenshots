"""Load the screenshot tool's JSON configuration and expose its public API."""

import json
import tempfile
from pathlib import Path

from .compose_config import _COMPOSE_TYPES as _COMPOSE_TYPES
from .compose_config import _FIT_KNOBS as _FIT_KNOBS
from .compose_config import _parse_compose
from .compose_config import parse_size as parse_size
from .config_errors import _fail as _fail
from .config_models import (
    ACCEPT_TIMEOUT_S as ACCEPT_TIMEOUT_S,
)
from .config_models import (
    DEFAULT_PIXEL_RATIO as DEFAULT_PIXEL_RATIO,
)
from .config_models import (
    ComposeStep as ComposeStep,
)
from .config_models import (
    DemoSpec,
    Settings,
)
from .config_models import (
    LaunchSettings as LaunchSettings,
)
from .config_models import (
    NetworkSettings as NetworkSettings,
)
from .config_models import (
    VerifyCheck as VerifyCheck,
)
from .demo_config import (
    _LANGUAGE_KEYS,
    _WINDOW_KEYS,
    _parse_demo_section,
)
from .demo_config import (
    _VALID_FORMATS as _VALID_FORMATS,
)
from .demo_config import (
    _parse_demo as _parse_demo,
)
from .demo_config import (
    _parse_launch as _parse_launch,
)
from .demo_config import (
    _parse_network as _parse_network,
)
from .demo_config import (
    _parse_verify as _parse_verify,
)
from .demo_config import (
    build_launch_command as build_launch_command,
)
from .demo_config import (
    write_app_settings_file as write_app_settings_file,
)
from .live_config import LiveSettings as LiveSettings
from .live_config import parse_live
from .web_config import WebSettings as WebSettings
from .web_config import parse_web

DEFAULT_CONFIG_PATH = Path(__file__).parent.parent / "config" / "keyboard-layout-watcher.json"
_ALWAYS_REQUIRED = ["output_dir"]


def expand(text: str, demo: "DemoSpec | None" = None, language: str | None = None) -> str:
    """Fill {temp}/{demo_id}/{name}/{lang} in a config path or env value."""
    values = {
        "temp": tempfile.gettempdir(),
        "demo_id": str(demo.id) if demo else "",
        "name": demo.name if demo else "",
        "lang": language or "",
    }
    for key, value in values.items():
        text = text.replace("{" + key + "}", value)
    return text


def load_config(path: str | Path | None = None) -> Settings:
    """Load an app config JSON and return (and remember) the Settings.

    Args:
        path: Path to config JSON. Defaults to DEFAULT_CONFIG_PATH.

    Raises:
        SystemExit: If the file is missing, invalid JSON, or lacks required keys.
    """
    global settings

    config_path = Path(path) if path else DEFAULT_CONFIG_PATH
    if not config_path.is_file():
        raise SystemExit(f"ERROR: Config file not found: {config_path}")

    try:
        data = json.loads(config_path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as e:
        raise SystemExit(f"ERROR: Invalid JSON in {config_path}: {e}") from e

    required = list(_ALWAYS_REQUIRED)
    if "languages" in data or "launch" in data:
        required += _WINDOW_KEYS
    if "languages" in data:
        required += _LANGUAGE_KEYS
    missing = [key for key in required if key not in data]
    if missing:
        raise SystemExit(f"ERROR: Config {config_path} is missing keys: {', '.join(missing)}")

    launch, network, demos = _parse_demo_section(config_path, data)
    live = parse_live(config_path, data["live"]) if "live" in data else None
    web = parse_web(config_path, data["web"]) if "web" in data else None
    compose = _parse_compose(config_path, data, demos)

    # A relative output_dir is relative to the config file, not to wherever the
    # tool happens to be run from - configs live next to the app they record.
    output_dir = Path(data["output_dir"])
    if not output_dir.is_absolute():
        output_dir = (config_path.parent / output_dir).resolve()

    texts_dir = data.get("texts_dir")
    if texts_dir is not None and not isinstance(texts_dir, str):
        raise SystemExit(f"ERROR: Config {config_path}: texts_dir must be a string")
    pause_fancyzones = data.get("pause_fancyzones", True)
    if not isinstance(pause_fancyzones, bool):
        raise SystemExit(f"ERROR: Config {config_path}: pause_fancyzones must be a boolean")

    has_languages = "languages" in data
    pos = data.get("dropdown_relative_pos")
    settings = Settings(
        process_name=data.get("process_name", ""),
        title_substring=data.get("title_substring", ""),
        output_dir=str(output_dir),
        dropdown_relative_pos=(int(pos[0]), int(pos[1])) if has_languages else None,
        screenshot_filename=data.get("screenshot_filename"),
        delay_after_change=float(data["delay_after_change"]) if has_languages else None,
        language_names=data.get("languages"),
        launch=launch,
        network=network,
        live=live,
        web=web,
        demos=demos,
        compose=compose,
        texts_dir=texts_dir,
        pause_fancyzones=pause_fancyzones,
    )
    return settings


settings: Settings = load_config()
