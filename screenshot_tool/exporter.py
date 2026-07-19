"""Export recorded window frames as animated GIF and MP4."""

from pathlib import Path

import numpy as np
from PIL import Image

# GIF renderers commonly treat <20ms per frame as "unspecified"
_MIN_FRAME_MS = 20
_SINGLE_FRAME_MS = 100


def frame_durations_ms(timestamps: list[float]) -> list[int]:
    """Per-frame display durations from capture timestamps.

    The last frame repeats the previous delta (there is no next timestamp).
    """
    if len(timestamps) <= 1:
        return [_SINGLE_FRAME_MS] * len(timestamps)
    deltas = [max(_MIN_FRAME_MS, round((b - a) * 1000)) for a, b in zip(timestamps, timestamps[1:])]
    return deltas + [deltas[-1]]


def export_gif(frames: list[Image.Image], timestamps: list[float], path: Path) -> None:
    """Write frames as a looping GIF with real capture timing."""
    path.parent.mkdir(parents=True, exist_ok=True)
    frames[0].save(
        path,
        save_all=True,
        append_images=frames[1:],
        duration=frame_durations_ms(timestamps),
        loop=0,
        optimize=True,
    )


def export_mp4(frames: list[Image.Image], fps: int, path: Path) -> None:
    """Write frames as an H.264 MP4 at the nominal capture fps."""
    import imageio.v2 as imageio

    path.parent.mkdir(parents=True, exist_ok=True)
    imageio.mimwrite(
        path,
        [np.asarray(frame.convert("RGB")) for frame in frames],
        fps=fps,
        codec="libx264",
        quality=8,
        # x264 (4:2:0) needs even dimensions. macro_block_size=2 pads an odd
        # side by 1px instead of rescaling to a multiple of 16 (the default),
        # so captures/crops of any size export without failing.
        macro_block_size=2,
    )
