"""Parsing and command helpers for recorded demo configuration."""

from pathlib import Path

from .config_errors import _fail
from .config_models import (
    ACCEPT_TIMEOUT_S,
    DEFAULT_PIXEL_RATIO,
    DemoSpec,
    LaunchSettings,
    NetworkSettings,
    Subtitle,
    VerifyCheck,
)

_VALID_FORMATS = ("gif", "mp4", "png")
_SCALE_KEY = "scale_to_window_size"
_MIN_SIZE_KEY = "min_capture_size"
_WINDOW_KEYS = ["process_name", "title_substring"]
_LANGUAGE_KEYS = ["dropdown_relative_pos", "screenshot_filename", "delay_after_change", "languages"]


def _parse_launch(config_path: Path, data: dict) -> LaunchSettings:
    command = data.get("command")
    has_valid_command = (
        isinstance(command, list)
        and bool(command)
        and all(isinstance(part, str) for part in command)
    )
    if not has_valid_command:
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
            has_file_and_text = isinstance(value, dict) and "file" in value and "text" in value
            if not has_file_and_text:
                _fail(config_path, f"demo '{name}' contains needs 'file' and 'text'")
            checks.append(VerifyCheck("contains", str(value["file"]), str(value["text"])))
        else:
            _fail(config_path, f"demo '{name}' has unknown verify check '{kind}'")
    return tuple(checks)


def _is_number(value: object) -> bool:
    # bool is an int subclass, and True as a time is a config typo, not 1 s.
    return isinstance(value, (int, float)) and not isinstance(value, bool)


def _parse_subtitles(config_path: Path, name: str, data: dict) -> tuple[Subtitle, ...]:
    raw = data.get("subtitles", [])
    if not isinstance(raw, list):
        _fail(config_path, f"demo '{name}' subtitles must be a list of objects")
    subtitles = []
    for entry in raw:
        if not isinstance(entry, dict):
            _fail(config_path, f"demo '{name}' subtitles must be a list of objects")
        at, text, seconds = entry.get("at"), entry.get("text"), entry.get("seconds")
        if not _is_number(at) or at < 0:
            _fail(config_path, f"demo '{name}' subtitle 'at' must be a number of seconds >= 0")
        if not isinstance(text, str) or not text:
            _fail(config_path, f"demo '{name}' subtitle at {at} needs a non-empty 'text'")
        if seconds is not None and (not _is_number(seconds) or seconds <= 0):
            _fail(config_path, f"demo '{name}' subtitle at {at} 'seconds' must be a number > 0")
        subtitles.append(Subtitle(float(at), text, None if seconds is None else float(seconds)))
    return tuple(subtitles)


def _parse_scale_flag(config_path: Path, value: object, where: str) -> bool:
    """Validate a scale-to-window-size flag and identify its config location."""
    if not isinstance(value, bool):
        _fail(config_path, f"{where} {_SCALE_KEY} must be a boolean")
    return value


def _parse_min_size(
    config_path: Path, value: object, where: str
) -> tuple[int, int] | None:
    """Validate an optional minimum saved-image size."""
    if value is None:
        return None
    if not isinstance(value, dict):
        _fail(config_path, f"{where} {_MIN_SIZE_KEY} must be an object or null")
    width, height = value.get("width"), value.get("height")
    valid_width = isinstance(width, int) and not isinstance(width, bool) and width > 0
    valid_height = isinstance(height, int) and not isinstance(height, bool) and height > 0
    if not valid_width or not valid_height:
        _fail(config_path, f"{where} {_MIN_SIZE_KEY} needs positive integer width and height")
    return width, height


def _parse_demo(
    config_path: Path,
    data: dict,
    scale_default: bool = False,
    min_size_default: tuple[int, int] | None = None,
) -> DemoSpec:
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
    raw_steps = data.get("steps", [])
    if not isinstance(raw_steps, list) or not all(
        isinstance(s, dict) and isinstance(s.get("type"), str) for s in raw_steps
    ):
        _fail(config_path, f"demo '{data['name']}' steps must be a list of objects with a 'type'")
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
        scale_to_window_size=_parse_scale_flag(
            config_path, data.get(_SCALE_KEY, scale_default), f"demo '{data['name']}'"
        ),
        min_capture_size=(
            _parse_min_size(config_path, data[_MIN_SIZE_KEY], f"demo '{data['name']}'")
            if _MIN_SIZE_KEY in data
            else min_size_default
        ),
        app_settings=tuple((str(k), str(v)) for k, v in raw_settings.items()),
        languages=tuple(raw_languages),
        crop=crop,
        verify=_parse_verify(config_path, data["name"], data),
        group=data.get("group"),
        caption=data.get("caption"),
        captions=tuple((str(k), str(v)) for k, v in raw_captions.items()),
        subtitles=_parse_subtitles(config_path, data["name"], data),
        pixel_ratio=float(data.get("pixel_ratio", DEFAULT_PIXEL_RATIO)),
        path=data.get("path", "/"),
        steps=tuple(raw_steps),
    )


def _parse_network(config_path: Path, data: dict) -> NetworkSettings:
    if not isinstance(data, dict) or not isinstance(data.get("port"), int):
        _fail(config_path, "network.port must be an integer")
    timeout = data.get("accept_timeout", ACCEPT_TIMEOUT_S)
    if not _is_number(timeout) or timeout <= 0:
        _fail(config_path, "network.accept_timeout must be a positive number of seconds")
    return NetworkSettings(port=data["port"], accept_timeout=float(timeout))


def _parse_demo_section(
    config_path: Path, data: dict
) -> tuple[LaunchSettings | None, NetworkSettings | None, tuple[DemoSpec, ...]]:
    if "demos" not in data:
        return None, None, ()
    modes = [mode for mode in ("launch", "network", "web") if mode in data]
    if len(modes) != 1:
        _fail(
            config_path,
            "'demos' requires exactly one of a 'launch', 'network' or 'web' section",
        )
    scale_default = _parse_scale_flag(config_path, data.get(_SCALE_KEY, False), "top-level")
    min_size_default = _parse_min_size(
        config_path, data.get(_MIN_SIZE_KEY), "top-level"
    )
    demos = tuple(
        _parse_demo(config_path, demo, scale_default, min_size_default)
        for demo in data["demos"]
    )
    if modes[0] == "web":
        if any(demo.min_capture_size is not None for demo in demos):
            _fail(config_path, f"{_MIN_SIZE_KEY} is only supported for launch demos")
        for demo in demos:
            if not isinstance(demo.path, str) or not demo.path.startswith("/"):
                _fail(config_path, f"demo '{demo.name}' path must start with '/'")
            if (demo.width is None) != (demo.height is None):
                _fail(config_path, f"web demo '{demo.name}' must set both width and height")
        return None, None, demos
    if "network" in data:
        if any(demo.min_capture_size is not None for demo in demos):
            _fail(config_path, f"{_MIN_SIZE_KEY} is only supported for launch demos")
        return None, _parse_network(config_path, data["network"]), demos
    launch = _parse_launch(config_path, data["launch"])

    missing_scale_size = [
        demo.name
        for demo in demos
        if demo.scale_to_window_size and (demo.width is None or demo.height is None)
    ]
    if missing_scale_size:
        _fail(
            config_path,
            f"{_SCALE_KEY} needs 'width' and 'height' on demo(s): "
            f"{', '.join(missing_scale_size)}",
        )

    oversized_minimum = [
        demo.name
        for demo in demos
        if demo.min_capture_size is not None
        and demo.max_output_size is not None
        and any(
            minimum > output
            for minimum, output in zip(demo.min_capture_size, demo.max_output_size, strict=True)
        )
    ]
    if oversized_minimum:
        _fail(
            config_path,
            f"{_MIN_SIZE_KEY} cannot exceed scaled output size for demo(s): "
            f"{', '.join(oversized_minimum)}",
        )

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
    return launch, None, demos
