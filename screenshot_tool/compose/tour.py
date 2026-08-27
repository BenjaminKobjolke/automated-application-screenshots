"""Join recorded chapters into one captioned tour, with Remotion.

Each chapter is recorded separately (the recorder holds every frame in RAM, so
one long take would need gigabytes). This renders them as a single composition
with a title over the start of each, plus optional opening and closing cards.

The render happens exactly once. A size budget is met afterwards by an ffmpeg
transcode, never by rendering again - Remotion is headless Chrome per frame,
and iterating it would cost more than everything else in the pipeline put
together.
"""

from __future__ import annotations

import json
import shutil
import subprocess
import tempfile
from pathlib import Path
from typing import Any

from .. import config
from ..app_logger import AppLogger
from ..config import ComposeStep, DemoSpec
from . import video
from .fit import encode_to_budget, format_size

COMPOSER_DIR = Path(__file__).resolve().parents[2] / "composer"
COMPOSITION_ID = "Tour"
DEFAULTS: dict[str, Any] = {"width": 1280, "fps": 30, "caption_seconds": 5.0, "crf": 18}
# Cards are short: they are a title, not a chapter.
CARD_SECONDS = 3.0


def _npx() -> str:
    """The npx executable, or a readable explanation of its absence."""
    found = shutil.which("npx")
    if not found:
        raise RuntimeError(
            "The 'tour' compose step renders with Remotion, which needs Node.js "
            "(18 or newer) on PATH - 'npx' was not found. Install Node, then run "
            "'npm install' in " + str(COMPOSER_DIR) + ". Recording and the GIF "
            "steps do not need Node."
        )
    return found


def _installed() -> None:
    if not (COMPOSER_DIR / "node_modules").is_dir():
        raise RuntimeError(
            f"Remotion is not installed yet - run 'npm install' in {COMPOSER_DIR}"
        )


def _clip_seconds(path: Path) -> float:
    """The clip's real duration, measured with the ffmpeg that is already here."""
    import imageio_ffmpeg

    _frames, seconds = imageio_ffmpeg.count_frames_and_secs(str(path))
    return float(seconds)


def _chapter_clip(demo: DemoSpec, language: str | None) -> Path:
    out = Path(config.settings.output_dir) / "demos" / demo.name
    if language:
        out = out / language
    path = out / "demo.mp4"
    if not path.is_file():
        raise RuntimeError(
            f"Missing {path} - record it first with: --demo {demo.id} "
            f"(the chapter also needs 'mp4' in its formats)"
        )
    return path


def _card(spec: Any, fps: int) -> dict[str, Any] | None:
    if not spec:
        return None
    return {
        "title": str(spec.get("title", "")),
        "subtitle": spec.get("subtitle"),
        "durationInFrames": int(CARD_SECONDS * fps),
    }


def _props(step: ComposeStep, chapters: tuple[DemoSpec, ...], language: str | None) -> dict:
    merged = {**DEFAULTS, **step.settings}
    fps = int(merged["fps"])
    width = int(merged["width"])
    public_dir = Path(config.settings.output_dir)

    clips: list[dict[str, Any]] = []
    height = None
    for demo in chapters:
        path = _chapter_clip(demo, language)
        clips.append(
            {
                # Relative to the public dir: Remotion serves files from there,
                # and an absolute Windows path is not a URL Chrome will load.
                "src": path.relative_to(public_dir).as_posix(),
                "durationInFrames": max(1, round(_clip_seconds(path) * fps)),
                "caption": demo.caption_for(language),
            }
        )
        if height is None and demo.width and demo.height:
            # Keep the recorded aspect ratio at the composition's width.
            height = round(width * demo.height / demo.width)

    intro = _card(merged.get("intro"), fps)
    outro = _card(merged.get("outro"), fps)
    total = sum(c["durationInFrames"] for c in clips)
    total += (intro or {}).get("durationInFrames", 0)
    total += (outro or {}).get("durationInFrames", 0)

    return {
        "fps": fps,
        "width": width,
        # -2-style rounding: H.264 needs even dimensions.
        "height": (height or round(width * 0.625)) // 2 * 2,
        "totalFrames": max(1, total),
        "captionFrames": max(1, round(float(merged["caption_seconds"]) * fps)),
        "clips": clips,
        "intro": intro,
        "outro": outro,
    }


def _render(props: dict, crf: int, destination: Path) -> None:
    """Run the Remotion render, streaming its output into the tool's log."""
    with tempfile.TemporaryDirectory() as work:
        props_file = Path(work) / "props.json"
        props_file.write_text(json.dumps(props), encoding="utf-8")
        command = [
            _npx(), "remotion", "render", "src/index.ts", COMPOSITION_ID, str(destination),
            f"--props={props_file}",
            # The recordings folder IS the public dir, so clips are referenced
            # where they already live instead of being copied in.
            f"--public-dir={Path(config.settings.output_dir)}",
            "--codec=h264",
            f"--crf={crf}",
            "--log=info",
        ]
        AppLogger.info(f"Rendering {len(props['clips'])} chapters with Remotion...")
        result = subprocess.run(command, cwd=str(COMPOSER_DIR), shell=False)
    if result.returncode:
        raise RuntimeError(f"Remotion render failed ({result.returncode})")


def _output_path(step: ComposeStep, language: str | None) -> Path:
    if language and "{lang}" not in step.output:
        raise RuntimeError(
            f"compose step '{step.output}' joins chapters recorded per language "
            f"but has no {{lang}} placeholder - every language would overwrite "
            f"the last"
        )
    return Path(config.settings.output_dir) / step.output.format(lang=language or "", name="tour")


def render_tour(step: ComposeStep) -> None:
    """Build the tour(s) this compose step describes."""
    _installed()
    chapters = config.settings.demos_in_group(step.group or "")
    if not chapters:
        raise RuntimeError(f"compose step '{step.output}' has no chapters in group {step.group!r}")
    languages = list(chapters[0].languages) if chapters[0].languages else [None]

    merged = {**DEFAULTS, **step.settings}
    for language in languages:
        props = _props(step, chapters, language)
        output = _output_path(step, language)
        output.parent.mkdir(parents=True, exist_ok=True)
        AppLogger.info("Chapters: " + ", ".join(d.name for d in chapters))
        with tempfile.TemporaryDirectory() as work:
            rendered = Path(work) / "tour.mp4"
            _render(props, int(merged["crf"]), rendered)
            _deliver(step, props, rendered, output)


def _deliver(step: ComposeStep, props: dict, rendered: Path, output: Path) -> None:
    """Move the render to its output, transcoding if it has a budget to meet."""
    if step.max_size is None:
        shutil.move(str(rendered), str(output))
        AppLogger.info(f"  {output} ({format_size(output.stat().st_size)})")
        return

    seconds = props["totalFrames"] / props["fps"]
    settings: dict[str, Any] = {}
    if step.fit_knobs:
        # One bitrate-targeted pass hits the budget outright; the search only
        # exists as a safety net for container overhead, so it never runs here.
        settings["bitrate"] = video.bitrate_for(seconds, step.max_size)
    else:
        settings["crf"] = int({**DEFAULTS, **step.settings}["crf"])

    result = encode_to_budget(
        lambda s, path: video.transcode_mp4(rendered, s, path),
        settings,
        output,
        max_bytes=step.max_size,
        fit=(),
        on_miss=step.on_miss,
    )
    AppLogger.info(f"  {output} ({format_size(result.size)})")
