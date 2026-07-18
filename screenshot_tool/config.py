"""Configuration for the screenshot tool, loaded from a JSON config file."""

import json
from dataclasses import dataclass, field
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


@dataclass(frozen=True)
class Settings:
    """Typed app configuration; the one object all modules read from."""

    process_name: str
    title_substring: str
    dropdown_relative_pos: tuple[int, int]
    output_dir: str
    screenshot_filename: str
    delay_after_change: float
    language_names: dict[str, str]
    language_codes: list[str] = field(init=False)
    name_to_code: dict[str, str] = field(init=False)

    def __post_init__(self) -> None:
        # Derived, not passed in: codes and reverse lookup always match language_names
        object.__setattr__(self, "language_codes", sorted(self.language_names))
        object.__setattr__(
            self, "name_to_code", {name: code for code, name in self.language_names.items()}
        )


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
        raise SystemExit(f"ERROR: Invalid JSON in {config_path}: {e}")

    missing = [key for key in _REQUIRED_KEYS if key not in data]
    if missing:
        raise SystemExit(f"ERROR: Config {config_path} is missing keys: {', '.join(missing)}")

    pos = data["dropdown_relative_pos"]
    settings = Settings(
        process_name=data["process_name"],
        title_substring=data["title_substring"],
        dropdown_relative_pos=(int(pos[0]), int(pos[1])),
        output_dir=data["output_dir"],
        screenshot_filename=data["screenshot_filename"],
        delay_after_change=float(data["delay_after_change"]),
        language_names=data["languages"],
    )
    return settings


settings: Settings = load_config()
