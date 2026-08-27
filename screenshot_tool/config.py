"""Configuration for the screenshot tool, loaded from a JSON config file.

A config may define a language-screenshot flow (``languages`` + dropdown keys),
animated demos (``launch`` + ``demos``), or both.
"""

import json
import tempfile
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, NoReturn

DEFAULT_CONFIG_PATH = Path(__file__).parent.parent / "config" / "keyboard-layout-watcher.json"

_ALWAYS_REQUIRED = ["process_name", "title_substring", "output_dir"]
_LANGUAGE_KEYS = ["dropdown_relative_pos", "screenshot_filename", "delay_after_change", "languages"]
_VALID_FORMATS = ("gif", "mp4")


@dataclass(frozen=True)
class LaunchSettings:
    """How to start the target application for a demo run."""

    command: tuple[str, ...]
    cwd: str | None
    # Environment for the child, with {temp}/{demo_id}/{name}/{lang} expanded.
    # Enough on its own to point an app at a throwaway profile without a
    # wrapper script.
    env: tuple[tuple[str, str], ...] = ()
    # The tool runs under uv, whose virtualenv is first on the child's PATH and
    # holds none of the app's dependencies. Set true only if the app really
    # wants the tool's environment.
    inherit_env: bool = False
    # Clear the desktop before the app starts; see WindowFinder.minimize_all.
    minimize_all: bool = True


@dataclass(frozen=True)
class VerifyCheck:
    """Evidence that a demo actually did what its script says it does.

    A demo can play to the end, report every event and still have missed - a
    dialog stole a keystroke, a viewer never took focus. Checking the side
    effect is the difference between a green run and a correct one.
    """

    kind: str
    path: str
    text: str | None = None

    def describe(self) -> str:
        if self.kind == "contains":
            return f"{self.path} contains {self.text!r}"
        return f"{self.path} exists"


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
    # Side effects that prove the demo landed, checked after it ends.
    verify: tuple[VerifyCheck, ...] = ()
    # Which compose step this demo feeds ("tour", "feature", ...). Replaces
    # matching on a name prefix, which no config could state and every
    # post-processing script had to re-implement.
    group: str | None = None
    # Title a "tour" compose step burns over this chapter; captions holds the
    # per-language wording, caption the single-language case.
    caption: str | None = None
    captions: tuple[tuple[str, str], ...] = ()

    @property
    def short_name(self) -> str:
        """The name without its group prefix: "feature-goto" -> "goto".

        Now that the group is a config field, the prefix in the name is
        redundant - but it is also what the published files are called, so
        {short} in a compose output keeps those filenames.
        """
        prefix = f"{self.group}-"
        return self.name[len(prefix):] if self.group and self.name.startswith(prefix) else self.name

    def caption_for(self, language: str | None) -> str | None:
        """This demo's caption in ``language``, falling back to ``caption``."""
        if language is not None:
            for code, text in self.captions:
                if code == language:
                    return text
        return self.caption


_COMPOSE_TYPES = ("tour", "stills_gif", "mp4_gif")
# Encoder knobs each step type may be told to trade away for a size budget.
_FIT_KNOBS = {
    "tour": ("crf", "width", "fps"),
    "stills_gif": ("lossy", "colors", "width"),
    "mp4_gif": ("lossy", "colors", "fps", "width"),
}
# Options each step type understands, beyond the shared keys.
_COMPOSE_OPTIONS = {
    "tour": ("width", "fps", "crf", "caption_seconds", "intro", "outro"),
    "stills_gif": ("width", "colors", "hold", "lossy"),
    "mp4_gif": ("width", "colors", "fps", "lossy"),
}
_SHARED_COMPOSE_KEYS = {"type", "output", "group", "demo", "max_size", "fit", "on_miss"}
_SIZE_UNITS = {"b": 1, "kb": 1000, "mb": 1000**2, "gb": 1000**3}


def parse_size(text: str | int) -> int:
    """Bytes from "2MB" / "500 KB" / 1500000.

    Raises:
        ValueError: The text is not a size.
    """
    if isinstance(text, int):
        return text
    cleaned = str(text).strip().lower().replace(" ", "")
    for unit in ("gb", "mb", "kb", "b"):
        if cleaned.endswith(unit):
            return int(float(cleaned[: -len(unit)]) * _SIZE_UNITS[unit])
    return int(float(cleaned))


@dataclass(frozen=True)
class ComposeStep:
    """One post-recording artifact: what to join, how, and how big it may be."""

    type: str
    output: str
    # Inputs: a demo group (every matching demo, in id order) or one demo name.
    group: str | None = None
    demo: str | None = None
    # Type-specific encoder settings (width, fps, colors, hold, captions...).
    options: tuple[tuple[str, Any], ...] = ()
    # Size budget in bytes, and the knobs the search may move to reach it.
    # Anything not in fit is a constraint. Empty fit = check and warn only.
    max_size: int | None = None
    fit: tuple[str, ...] | None = None
    on_miss: str = "warn"

    @property
    def settings(self) -> dict[str, Any]:
        """The options as a plain dict, for the encoder."""
        return dict(self.options)

    @property
    def fit_knobs(self) -> tuple[str, ...]:
        """The knobs the size search may move, defaulted per step type."""
        return _FIT_KNOBS[self.type] if self.fit is None else self.fit


def _parse_compose_step(config_path: Path, data: dict) -> ComposeStep:
    step_type = data.get("type")
    if step_type not in _COMPOSE_TYPES:
        _fail(
            config_path,
            f"compose step has type {step_type!r}; expected one of {', '.join(_COMPOSE_TYPES)}",
        )
    label = data.get("output") or step_type
    if not isinstance(data.get("output"), str) or not data["output"]:
        _fail(config_path, f"compose step {label!r} needs a non-empty 'output'")
    if bool(data.get("group")) == bool(data.get("demo")):
        _fail(config_path, f"compose step {label!r} needs exactly one of 'group' or 'demo'")

    known = set(_COMPOSE_OPTIONS[step_type])
    options = {k: v for k, v in data.items() if k in known}
    unknown = set(data) - known - _SHARED_COMPOSE_KEYS
    if unknown:
        _fail(
            config_path,
            f"compose step {label!r} has option(s) {', '.join(sorted(unknown))} that "
            f"{step_type!r} does not use (it takes: {', '.join(sorted(known))})",
        )

    max_size = None
    if "max_size" in data:
        try:
            max_size = parse_size(data["max_size"])
        except ValueError:
            _fail(config_path, f"compose step {label!r} has an unreadable max_size")
        if max_size <= 0:
            _fail(config_path, f"compose step {label!r} max_size must be positive")

    fit = None
    if "fit" in data:
        raw_fit = data["fit"]
        if not isinstance(raw_fit, list) or not all(isinstance(k, str) for k in raw_fit):
            _fail(config_path, f"compose step {label!r} fit must be a list of knob names")
        allowed = _FIT_KNOBS[step_type]
        bad = [k for k in raw_fit if k not in allowed]
        if bad:
            _fail(
                config_path,
                f"compose step {label!r} cannot fit {', '.join(bad)}; "
                f"{step_type!r} can trade {', '.join(allowed)}",
            )
        fit = tuple(raw_fit)
        if fit and max_size is None:
            _fail(config_path, f"compose step {label!r} sets 'fit' but no 'max_size'")

    on_miss = data.get("on_miss", "warn")
    if on_miss not in ("warn", "error"):
        _fail(config_path, f"compose step {label!r} on_miss must be 'warn' or 'error'")

    return ComposeStep(
        type=step_type,
        output=data["output"],
        group=data.get("group"),
        demo=data.get("demo"),
        options=tuple(options.items()),
        max_size=max_size,
        fit=fit,
        on_miss=on_miss,
    )


def _parse_compose(
    config_path: Path, data: dict, demos: tuple[DemoSpec, ...]
) -> tuple[ComposeStep, ...]:
    raw = data.get("compose", [])
    if not isinstance(raw, list):
        _fail(config_path, "'compose' must be a list of steps")
    steps = tuple(_parse_compose_step(config_path, d) for d in raw)
    if steps and not demos:
        _fail(config_path, "'compose' needs a 'demos' section to draw its clips from")

    # A step pointing at nothing is a silent no-op that reads like a build.
    names = {d.name for d in demos}
    groups = {d.group for d in demos if d.group}
    for step in steps:
        if step.demo and step.demo not in names:
            _fail(
                config_path,
                f"compose step {step.output!r} names demo {step.demo!r}, which no demo has "
                f"(demos: {', '.join(sorted(names))})",
            )
        if step.group and step.group not in groups:
            _fail(
                config_path,
                f"compose step {step.output!r} names group {step.group!r}, which no demo is in "
                f"(groups: {', '.join(sorted(groups)) or 'none'})",
            )
        if step.type == "tour":
            uncaptioned = [
                d.name for d in demos if d.group == step.group and not (d.caption or d.captions)
            ]
            if uncaptioned:
                _fail(
                    config_path,
                    f"compose step {step.output!r} is a tour but these chapters have no "
                    f"caption: {', '.join(uncaptioned)}",
                )
    return steps


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
    compose: tuple[ComposeStep, ...] = ()
    # Folder with per-language demo text files (<texts_dir>/<lang>.json)
    texts_dir: str | None = None
    language_codes: list[str] = field(init=False)
    name_to_code: dict[str, str] = field(init=False)

    def __post_init__(self) -> None:
        # Derived, not passed in: codes and reverse lookup always match language_names
        names = self.language_names or {}
        object.__setattr__(self, "language_codes", sorted(names))
        object.__setattr__(self, "name_to_code", {name: code for code, name in names.items()})

    def demos_in_group(self, group: str) -> tuple[DemoSpec, ...]:
        """The demos of ``group``, in id order - which is chapter order."""
        return tuple(sorted((d for d in self.demos if d.group == group), key=lambda d: d.id))

    def demo_named(self, name: str) -> DemoSpec | None:
        return next((d for d in self.demos if d.name == name), None)


def _fail(config_path: Path, message: str) -> NoReturn:
    raise SystemExit(f"ERROR: Config {config_path}: {message}")


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


def _parse_launch(config_path: Path, data: dict) -> LaunchSettings:
    command = data.get("command")
    if not isinstance(command, list) or not command or not all(isinstance(c, str) for c in command):
        _fail(config_path, "launch.command must be a non-empty list of strings")
    raw_env = data.get("env", {})
    if not isinstance(raw_env, dict):
        _fail(config_path, "launch.env must be an object of NAME -> value")
    return LaunchSettings(
        command=tuple(command),
        cwd=data.get("cwd"),
        env=tuple((str(k), str(v)) for k, v in raw_env.items()),
        inherit_env=bool(data.get("inherit_env", False)),
        minimize_all=bool(data.get("minimize_all", True)),
    )


def _parse_verify(config_path: Path, name: str, data: dict) -> tuple[VerifyCheck, ...]:
    raw = data.get("verify", [])
    if not isinstance(raw, list):
        _fail(config_path, f"demo '{name}' verify must be a list of checks")
    checks = []
    for entry in raw:
        if not isinstance(entry, dict) or len(entry) != 1:
            _fail(config_path, f"demo '{name}' verify entries are one of: exists, contains")
        kind, value = next(iter(entry.items()))
        if kind == "exists":
            checks.append(VerifyCheck("exists", str(value)))
        elif kind == "contains":
            if not isinstance(value, dict) or "file" not in value or "text" not in value:
                _fail(config_path, f"demo '{name}' contains needs 'file' and 'text'")
            checks.append(VerifyCheck("contains", str(value["file"]), str(value["text"])))
        else:
            _fail(config_path, f"demo '{name}' has unknown verify check '{kind}'")
    return tuple(checks)


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
    raw_captions = data.get("captions", {})
    if not isinstance(raw_captions, dict):
        _fail(config_path, f"demo '{data['name']}' captions must be an object of lang -> text")
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
        verify=_parse_verify(config_path, data["name"], data),
        group=data.get("group"),
        caption=data.get("caption"),
        captions=tuple((str(k), str(v)) for k, v in raw_captions.items()),
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
    compose = _parse_compose(config_path, data, demos)

    # A relative output_dir is relative to the config file, not to wherever the
    # tool happens to be run from - configs live next to the app they record.
    output_dir = Path(data["output_dir"])
    if not output_dir.is_absolute():
        output_dir = (config_path.parent / output_dir).resolve()

    texts_dir = data.get("texts_dir")
    if texts_dir is not None and not isinstance(texts_dir, str):
        raise SystemExit(f"ERROR: Config {config_path}: texts_dir must be a string")

    has_languages = "languages" in data
    pos = data.get("dropdown_relative_pos")
    settings = Settings(
        process_name=data["process_name"],
        title_substring=data["title_substring"],
        output_dir=str(output_dir),
        dropdown_relative_pos=(int(pos[0]), int(pos[1])) if has_languages else None,
        screenshot_filename=data.get("screenshot_filename"),
        delay_after_change=float(data["delay_after_change"]) if has_languages else None,
        language_names=data.get("languages"),
        launch=launch,
        demos=demos,
        compose=compose,
        texts_dir=texts_dir,
    )
    return settings


settings: Settings = load_config()
