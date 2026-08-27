"""GIF encoders: a slideshow of stills, and a recorded clip re-encoded.

Both exist because GitHub renders a video player only for a bare attachment
URL on a line of its own - a GIF is the only moving image that can sit next to
a paragraph in a README.
"""

from __future__ import annotations

import shutil
import subprocess
import tempfile
from pathlib import Path
from typing import Any

from ..app_logger import AppLogger
from . import ffmpeg

STILLS_DEFAULTS: dict[str, Any] = {"width": 960, "colors": 256, "hold": 2.0, "lossy": 0}
CLIP_DEFAULTS: dict[str, Any] = {"width": 800, "colors": 64, "fps": 5, "lossy": 0}


def _optimize(path: Path, lossy: int) -> None:
    """Shrink a finished GIF with gifsicle, if it is installed.

    The one lever ffmpeg does not have. It earns its place on clips where every
    pixel changes every frame - an animation, a video behind the UI - because
    there inter-frame compression buys nothing and each frame is stored whole;
    fewer colours and no dithering barely move such a file, and gifsicle's
    lossy quantisation roughly halves it.

    Optional on purpose: without gifsicle the pipeline still produces a correct
    GIF, just a larger one, so nobody is blocked on installing a second binary.
    """
    if not lossy:
        return
    binary = shutil.which("gifsicle")
    if not binary:
        AppLogger.warning(
            "WARNING: 'lossy' is set but gifsicle is not on PATH - keeping the "
            "unoptimized GIF (install gifsicle to shrink it)"
        )
        return
    optimized = path.with_suffix(".opt.gif")
    result = subprocess.run(
        [binary, "-O3", f"--lossy={int(lossy)}", "-o", str(optimized), str(path)],
        capture_output=True,
        text=True,
    )
    if result.returncode or not optimized.is_file():
        AppLogger.warning(f"WARNING: gifsicle failed, keeping the plain GIF: {result.stderr}")
        optimized.unlink(missing_ok=True)
        return
    optimized.replace(path)


def _write_concat_list(path: Path, images: list[Path], hold: float) -> None:
    """An ffmpeg concat-demuxer list holding each still for ``hold`` seconds.

    A list file rather than one -i per image because the names are content
    (theme names contain spaces). Paths are absolute and forward-slashed: the
    demuxer resolves a relative entry against the list file's own directory,
    not the working directory, and reads a backslash as an escape. The last
    entry is repeated because the demuxer ignores the final ``duration``.
    """
    lines = []
    for image in images:
        lines.append(f"file '{image.as_posix()}'")
        lines.append(f"duration {hold}")
    lines.append(f"file '{images[-1].as_posix()}'")
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def stills_to_gif(stills: list[Path], settings: dict[str, Any], output: Path) -> None:
    """Join PNG stills into a looping GIF, each held for ``hold`` seconds."""
    merged = {**STILLS_DEFAULTS, **settings}
    hold = float(merged["hold"])
    width = int(merged["width"])
    colors = int(merged["colors"])
    # fps is the reciprocal of the hold, so each still becomes exactly one GIF
    # frame carrying the whole delay - 11 frames, not 11 x fps copies of the
    # same picture. palettegen/paletteuse because a GIF's default 216-colour
    # web palette bands a flat background, which is usually the thing a
    # slideshow of stills exists to show.
    graph = (
        f"fps={1 / hold},scale={width}:-2:flags=lanczos,split[a][b];"
        f"[a]palettegen=stats_mode=diff:max_colors={colors}[p];[b][p]paletteuse"
    )
    with tempfile.TemporaryDirectory() as work:
        list_file = Path(work) / "stills.txt"
        _write_concat_list(list_file, stills, hold)
        ffmpeg.run(
            [
                "-f", "concat", "-safe", "0", "-i", str(list_file),
                "-filter_complex", graph,
                # The list repeats its last entry, which would otherwise leave
                # the final still on screen for two holds instead of one.
                "-t", str(len(stills) * hold),
                "-loop", "0",
                str(output),
            ]
        )
    _optimize(output, int(merged.get("lossy", 0)))


def clip_to_gif(source: Path, settings: dict[str, Any], output: Path) -> None:
    """Re-encode a recorded MP4 as a GIF, two-pass for a decent palette."""
    merged = {**CLIP_DEFAULTS, **settings}
    width = int(merged["width"])
    colors = int(merged["colors"])
    fps = int(merged["fps"])
    scale = f"fps={fps},scale={width}:-1:flags=lanczos"
    with tempfile.TemporaryDirectory() as work:
        palette = Path(work) / "palette.png"
        ffmpeg.run(
            ["-i", str(source), "-vf", f"{scale},palettegen=max_colors={colors}", str(palette)]
        )
        ffmpeg.run(
            [
                "-i", str(source), "-i", str(palette),
                # Bayer dithering keeps the file small; the default error
                # diffusion invents per-frame noise that no palette can share.
                "-lavfi", f"{scale} [x]; [x][1:v] paletteuse=dither=bayer:bayer_scale=5",
                "-loop", "0",
                str(output),
            ]
        )
    _optimize(output, int(merged.get("lossy", 0)))
