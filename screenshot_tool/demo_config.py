"""Parsing and command helpers for recorded demo configuration."""

from pathlib import Path

from .config_errors import _fail
from .config_models import (
    ACCEPT_TIMEOUT_S,
    DEFAULT_PIXEL_RATIO,
    DemoSpec,
    LaunchSettings,
    NetworkSettings,
    VerifyCheck,
)

_VALID_FORMATS = ("gif", "mp4", "png")
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
        app_settings=tuple((str(k), str(v)) for k, v in raw_settings.items()),
        languages=tuple(raw_languages),
        crop=crop,
        verify=_parse_verify(config_path, data["name"], data),
        group=data.get("group"),
        caption=data.get("caption"),
        captions=tuple((str(k), str(v)) for k, v in raw_captions.items()),
        pixel_ratio=float(data.get("pixel_ratio", DEFAULT_PIXEL_RATIO)),
        path=data.get("path", "/"),
        steps=tuple(raw_steps),
    )


def _parse_network(config_path: Path, data: dict) -> NetworkSettings:
    if not isinstance(data, dict) or not isinstance(data.get("port"), int):
        _fail(config_path, "network.port must be an integer")
    timeout = data.get("accept_timeout", ACCEPT_TIMEOUT_S)
    # bool is an int subclass, and True as a timeout is a config typo, not 1 s.
    is_positive_timeout = (
        not isinstance(timeout, bool) and isinstance(timeout, (int, float)) and timeout > 0
    )
    if not is_positive_timeout:
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
    demos = tuple(_parse_demo(config_path, d) for d in data["demos"])
    if modes[0] == "web":
        for demo in demos:
            if not isinstance(demo.path, str) or not demo.path.startswith("/"):
                _fail(config_path, f"demo '{demo.name}' path must start with '/'")
            if (demo.width is None) != (demo.height is None):
                _fail(config_path, f"web demo '{demo.name}' must set both width and height")
        return None, None, demos
    if "network" in data:
        return None, _parse_network(config_path, data["network"]), demos
    launch = _parse_launch(config_path, data["launch"])

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
