"""H.264 transcoding, for meeting a size budget after a render."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from . import ffmpeg

# Container overhead and rate-control slop; without it a bitrate aimed exactly
# at the budget lands a few percent over it.
_BUDGET_HEADROOM = 0.94


def bitrate_for(seconds: float, max_bytes: int) -> int:
    """Video bitrate in bits/s that lands ``seconds`` of video inside a budget."""
    return max(100_000, int(max_bytes * 8 / max(seconds, 0.1) * _BUDGET_HEADROOM))


def transcode_mp4(source: Path, settings: dict[str, Any], output: Path) -> None:
    """Re-encode an MP4, either at a quality (crf) or at a bitrate.

    A bitrate hits a target size in one pass, which is why a tour never needs
    the search: the budget is arithmetic on the duration, not a guess.
    """
    filters = []
    if settings.get("width"):
        # -2 keeps the height even, which 4:2:0 H.264 requires.
        filters.append(f"scale={int(settings['width'])}:-2:flags=lanczos")
    if settings.get("fps"):
        filters.append(f"fps={int(settings['fps'])}")

    args = ["-i", str(source)]
    if filters:
        args += ["-vf", ",".join(filters)]
    if settings.get("bitrate"):
        # Plain ABR, deliberately without -maxrate/-bufsize. Capping the peak
        # rate makes x264 conservative on easy content: measured on the fman
        # tour, the cap spent 68% of a 3 MB budget where plain ABR spent 93%,
        # and the difference is quality thrown away for a VBV guarantee a
        # README video does not need.
        args += ["-b:v", str(int(settings["bitrate"]))]
    else:
        args += ["-crf", str(int(settings.get("crf", 23)))]
    args += [
        "-c:v", "libx264",
        "-preset", "slow",
        "-pix_fmt", "yuv420p",
        "-movflags", "+faststart",
        "-an",
        str(output),
    ]
    ffmpeg.run(args)
