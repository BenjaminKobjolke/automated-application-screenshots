"""Running ffmpeg.

The binary comes from imageio-ffmpeg, which is already a dependency (the MP4
exporter uses it). Nothing here needs ffmpeg on PATH.
"""

from __future__ import annotations

import subprocess
from functools import lru_cache
from pathlib import Path

from ..app_logger import AppLogger

# Tail of ffmpeg's output kept for an error message: the real complaint is
# always in the last few lines, the rest is the build banner.
_ERROR_LINES = 12


@lru_cache(maxsize=1)
def binary() -> str:
    """Path to the bundled ffmpeg executable."""
    import imageio_ffmpeg

    return str(imageio_ffmpeg.get_ffmpeg_exe())


def run(args: list[str], cwd: Path | None = None) -> None:
    """Run ffmpeg with ``args`` (without the binary or -y).

    Raises:
        RuntimeError: ffmpeg exited non-zero.
    """
    command = [binary(), "-y", "-hide_banner", "-loglevel", "error", *args]
    AppLogger.debug(" ".join(command))
    result = subprocess.run(
        command,
        cwd=str(cwd) if cwd else None,
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
    )
    if result.returncode:
        tail = "\n".join((result.stderr or "").strip().splitlines()[-_ERROR_LINES:])
        raise RuntimeError(f"ffmpeg failed ({result.returncode}):\n{tail}")
