"""Configuration for the screenshot tool, loaded from a JSON config file."""

import json
from pathlib import Path

DEFAULT_CONFIG_PATH = Path(__file__).parent.parent / "config" / "keyboard-layout-watcher.json"

_REQUIRED_KEYS = [
    "process_name",
    "title_substring",
    "dropdown_relative_pos",
    "output_dir",
    "screenshot_filename",
    "delay_after_change",
    "languages",
]


def load_config(path: str | Path | None = None) -> None:
    """Load an app config JSON and populate module attributes.

    Args:
        path: Path to config JSON. Defaults to DEFAULT_CONFIG_PATH.

    Raises:
        SystemExit: If the file is missing, invalid JSON, or lacks required keys.
    """
    global APP_PROCESS_NAME, APP_TITLE_SUBSTRING, DROPDOWN_RELATIVE_POS
    global LANGUAGE_CODES, LANGUAGE_NAMES, NAME_TO_CODE
    global DEFAULT_OUTPUT_DIR, SCREENSHOT_FILENAME, DELAY_AFTER_CHANGE

    config_path = Path(path) if path else DEFAULT_CONFIG_PATH
    if not config_path.is_file():
        raise SystemExit(f"ERROR: Config file not found: {config_path}")

    try:
        data = json.loads(config_path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as e:
        raise SystemExit(f"ERROR: Invalid JSON in {config_path}: {e}")

    missing = [key for key in _REQUIRED_KEYS if key not in data]
    if missing:
        raise SystemExit(f"ERROR: Config {config_path} is missing keys: {', '.join(missing)}")

    APP_PROCESS_NAME = data["process_name"]
    APP_TITLE_SUBSTRING = data["title_substring"]
    DROPDOWN_RELATIVE_POS = tuple(data["dropdown_relative_pos"])
    LANGUAGE_NAMES = data["languages"]
    LANGUAGE_CODES = sorted(LANGUAGE_NAMES)
    NAME_TO_CODE = {name: code for code, name in LANGUAGE_NAMES.items()}
    DEFAULT_OUTPUT_DIR = data["output_dir"]
    SCREENSHOT_FILENAME = data["screenshot_filename"]
    DELAY_AFTER_CHANGE = float(data["delay_after_change"])


load_config()
