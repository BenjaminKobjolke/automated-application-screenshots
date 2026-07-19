"""Configuration for the screenshot tool, loaded from a JSON config file.

A config may define a language-screenshot flow (``languages`` + dropdown keys),
animated demos (``launch`` + ``demos``), or both.
"""

import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import NoReturn

DEFAULT_CONFIG_PATH = Path(__file__).parent.parent / "config" / "keyboard-layout-watcher.json"

_ALWAYS_REQUIRED = ["process_name", "title_substring", "output_dir"]
_LANGUAGE_KEYS = ["dropdown_relative_pos", "screenshot_filename", "delay_after_change", "languages"]
_VALID_FORMATS = ("gif", "mp4")


@dataclass(frozen=True)
class LaunchSettings:
    """How to start the target application for a demo run."""

    command: tuple[str, ...]
    cwd: str | None


@dataclass(frozen=True)
class DemoSpec:
    """One recordable demo the target application can play."""

    id: int
    name: str
    fps: int = 10
    formats: tuple[str, ...] = ("gif",)
    width: int | None = None
    height: int | None = None
    # Opaque app-specific settings, written to a JSON file the app receives
    # via --automation-demo-settings
    app_settings: tuple[tuple[str, str], ...] = ()
    # Record once per language ("en", "de", ...); empty = one run, no lang folder
    languages: tuple[str, ...] = ()
    # Pixels removed from each captured frame, (top, right, bottom, left).
    # For residual edge cleanup after the DWM/work-area capture bounds.
    crop: tuple[int, int, int, int] = (0, 0, 0, 0)


@dataclass(frozen=True)
class Settings:
    """Typed app configuration; the one object all modules read from."""

    process_name: str
    title_substring: str
    output_dir: str
    dropdown_relative_pos: tuple[int, int] | None = None
    screenshot_filename: str | None = None
    delay_after_change: float | None = None
    language_names: dict[str, str] | None = None
    launch: LaunchSettings | None = None
    demos: tuple[DemoSpec, ...] = ()
    # Folder with per-language demo text files (<texts_dir>/<lang>.json)
    texts_dir: str | None = None
    language_codes: list[str] = field(init=False)
    name_to_code: dict[str, str] = field(init=False)

    def __post_init__(self) -> None:
        # Derived, not passed in: codes and reverse lookup always match language_names
        names = self.language_names or {}
        object.__setattr__(self, "language_codes", sorted(names))
        object.__setattr__(self, "name_to_code", {name: code for code, name in names.items()})


def _fail(config_path: Path, message: str) -> NoReturn:
    raise SystemExit(f"ERROR: Config {config_path}: {message}")


def _parse_launch(config_path: Path, data: dict) -> LaunchSettings:
    command = data.get("command")
    if not isinstance(command, list) or not command or not all(isinstance(c, str) for c in command):
        _fail(config_path, "launch.command must be a non-empty list of strings")
    return LaunchSettings(command=tuple(command), cwd=data.get("cwd"))


def _parse_demo(config_path: Path, data: dict) -> DemoSpec:
    if not isinstance(data.get("id"), int):
        _fail(config_path, "each demo needs an integer 'id'")
    if not isinstance(data.get("name"), str) or not data["name"]:
        _fail(config_path, f"demo {data['id']} needs a non-empty 'name'")
    formats = tuple(data.get("formats", ["gif"]))
    invalid = [f for f in formats if f not in _VALID_FORMATS]
    if invalid:
        _fail(config_path, f"demo '{data['name']}' has invalid format(s): {', '.join(invalid)}")
    raw_settings = data.get("app_settings", {})
    if not isinstance(raw_settings, dict):
        _fail(config_path, f"demo '{data['name']}' app_settings must be an object")
    raw_languages = data.get("languages", [])
    if not isinstance(raw_languages, list) or not all(
        isinstance(lang, str) and lang for lang in raw_languages
    ):
        _fail(config_path, f"demo '{data['name']}' languages must be a list of non-empty strings")
    raw_crop = data.get("crop", {})
    if not isinstance(raw_crop, dict):
        _fail(
            config_path, f"demo '{data['name']}' crop must be an object with top/right/bottom/left"
        )
    crop = (
        max(0, int(raw_crop.get("top", 0))),
        max(0, int(raw_crop.get("right", 0))),
        max(0, int(raw_crop.get("bottom", 0))),
        max(0, int(raw_crop.get("left", 0))),
    )
    return DemoSpec(
        id=data["id"],
        name=data["name"],
        fps=int(data.get("fps", 10)),
        formats=formats,
        width=data.get("width"),
        height=data.get("height"),
        app_settings=tuple((str(k), str(v)) for k, v in raw_settings.items()),
        languages=tuple(raw_languages),
        crop=crop,
    )


def _parse_demo_section(
    config_path: Path, data: dict
) -> tuple[LaunchSettings | None, tuple[DemoSpec, ...]]:
    if "demos" not in data:
        return None, ()
    if "launch" not in data:
        _fail(config_path, "'demos' requires a 'launch' section")
    launch = _parse_launch(config_path, data["launch"])
    demos = tuple(_parse_demo(config_path, d) for d in data["demos"])

    # A {width}/{height} placeholder in the command needs a size on every demo
    command_text = " ".join(launch.command)
    for placeholder, attr in (("{width}", "width"), ("{height}", "height")):
        if placeholder in command_text:
            unsized = [d.name for d in demos if getattr(d, attr) is None]
            if unsized:
                _fail(
                    config_path,
                    f"launch.command uses {placeholder} but demo(s) missing '{attr}': "
                    f"{', '.join(unsized)}",
                )
    return launch, demos


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

    required = list(_ALWAYS_REQUIRED)
    if "languages" in data:
        required += _LANGUAGE_KEYS
    missing = [key for key in required if key not in data]
    if missing:
        raise SystemExit(f"ERROR: Config {config_path} is missing keys: {', '.join(missing)}")

    launch, demos = _parse_demo_section(config_path, data)

    texts_dir = data.get("texts_dir")
    if texts_dir is not None and not isinstance(texts_dir, str):
        raise SystemExit(f"ERROR: Config {config_path}: texts_dir must be a string")

    has_languages = "languages" in data
    pos = data.get("dropdown_relative_pos")
    settings = Settings(
        process_name=data["process_name"],
        title_substring=data["title_substring"],
        output_dir=data["output_dir"],
        dropdown_relative_pos=(int(pos[0]), int(pos[1])) if has_languages else None,
        screenshot_filename=data.get("screenshot_filename"),
        delay_after_change=float(data["delay_after_change"]) if has_languages else None,
        language_names=data.get("languages"),
        launch=launch,
        demos=demos,
        texts_dir=texts_dir,
    )
    return settings


settings: Settings = load_config()
