"""Post-recording composition: turn recorded clips and stills into artifacts.

Recording produces intermediates - one clip per chapter, one still per theme.
The ``compose`` section of the config says what to build out of them, so the
chain that used to be a folder of batch files is one flag: ``--compose``.
"""

from __future__ import annotations

from pathlib import Path

from .. import config
from ..app_logger import AppLogger
from ..config import ComposeStep, DemoSpec
from . import gif
from .fit import encode_to_budget, format_size


def _runs(demo: DemoSpec) -> list[str | None]:
    """The languages this demo was recorded in; ``[None]`` when it has none."""
    return list(demo.languages) if demo.languages else [None]


def _demo_dir(demo: DemoSpec, language: str | None) -> Path:
    out = Path(config.settings.output_dir) / "demos" / demo.name
    return out / language if language else out


def _output_path(step: ComposeStep, demo: DemoSpec, language: str | None) -> Path:
    template = step.output
    if language and "{lang}" not in template:
        raise RuntimeError(
            f"compose step '{template}' reads demo '{demo.name}', which is recorded per "
            f"language, but its output has no {{lang}} placeholder - every language "
            f"would overwrite the last"
        )
    rendered = template.format(name=demo.name, short=demo.short_name, lang=language or "")
    return Path(config.settings.output_dir) / rendered


def _require(path: Path, demo: DemoSpec, what: str) -> Path:
    if not path.is_file():
        raise RuntimeError(
            f"Missing {path} - record it first with: --config <config> --demo {demo.id} ({what})"
        )
    return path


def _step_demos(step: ComposeStep) -> tuple[DemoSpec, ...]:
    if step.group:
        return config.settings.demos_in_group(step.group)
    demo = config.settings.demo_named(step.demo or "")
    return (demo,) if demo else ()


def _encode_to_budget(step: ComposeStep, encode, settings: dict, output: Path) -> None:
    result = encode_to_budget(
        encode,
        settings,
        output,
        max_bytes=step.max_size,
        fit=step.fit_knobs if step.max_size else (),
        on_miss=step.on_miss,
    )
    AppLogger.info(f"  {output} ({format_size(result.size)})")


def _run_stills_gif(step: ComposeStep) -> None:
    for demo in _step_demos(step):
        for language in _runs(demo):
            stills = sorted(_demo_dir(demo, language).glob("*.png"))
            if not stills:
                raise RuntimeError(
                    f"No stills in {_demo_dir(demo, language)} - record them first "
                    f"with: --demo {demo.id}"
                )
            output = _output_path(step, demo, language)
            AppLogger.info(
                f"Joining {len(stills)} stills: {', '.join(s.stem for s in stills)}"
            )
            _encode_to_budget(
                step,
                lambda settings, path, stills=stills: gif.stills_to_gif(stills, settings, path),
                {**gif.STILLS_DEFAULTS, **step.settings},
                output,
            )


def _run_clip_gif(step: ComposeStep) -> None:
    for demo in _step_demos(step):
        for language in _runs(demo):
            source = _require(_demo_dir(demo, language) / "demo.mp4", demo, "needs an mp4 format")
            output = _output_path(step, demo, language)
            _encode_to_budget(
                step,
                lambda settings, path, source=source: gif.clip_to_gif(source, settings, path),
                {**gif.CLIP_DEFAULTS, **step.settings},
                output,
            )


def _run_tour(step: ComposeStep) -> None:
    from .tour import render_tour

    render_tour(step)


_RUNNERS = {
    "stills_gif": _run_stills_gif,
    "mp4_gif": _run_clip_gif,
    "tour": _run_tour,
}


def select(selector: str) -> tuple[ComposeStep, ...]:
    """The configured steps ``selector`` names ("all", or part of an output path)."""
    steps = config.settings.compose
    if selector == "all":
        return steps
    matched = tuple(s for s in steps if selector in s.output or selector == s.type)
    if not matched:
        available = ", ".join(s.output for s in steps) or "none"
        raise SystemExit(f"ERROR: No compose step matches '{selector}' (have: {available})")
    return matched


def run(selector: str = "all") -> int:
    """Build the selected compose steps.

    Returns:
        Exit code (0 when every selected step succeeded).
    """
    if not config.settings.compose:
        AppLogger.error("Config has no 'compose' section - nothing to build.")
        return 1
    steps = select(selector)
    failed = []
    for step in steps:
        AppLogger.info(f"\n--- Compose '{step.output}' ({step.type}) ---")
        try:
            _RUNNERS[step.type](step)
        except (RuntimeError, OSError) as e:
            AppLogger.error(str(e))
            failed.append(step.output)
    AppLogger.info(f"\n{'=' * 50}")
    AppLogger.info(f"Compose complete: {len(steps) - len(failed)}/{len(steps)} succeeded")
    for name in failed:
        AppLogger.info(f"  FAILED: {name}")
    return 0 if not failed else 1
