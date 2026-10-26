"""Parsing and validation for post-recording composition steps."""

from pathlib import Path

from .config_errors import _fail
from .config_models import _FIT_KNOBS, ComposeStep, DemoSpec

_COMPOSE_TYPES = ("tour", "stills_gif", "mp4_gif")
# Encoder knobs each step type may be told to trade away for a size budget.
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
