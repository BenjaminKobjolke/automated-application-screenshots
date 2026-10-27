"""Quality ladders and size predictions for budgeted composition."""

from __future__ import annotations

import math
from collections.abc import Iterable
from typing import Any

MIN_WIDTH = 320
_WIDTH_STEP = 0.8

# Best-first. A knob never starts better than the value the config asked for.
_LADDERS: dict[str, tuple[int, ...]] = {
    "fps": (30, 25, 20, 15, 12, 10, 8, 6, 5, 4, 3),
    "colors": (256, 192, 128, 96, 64, 48, 32, 24, 16),
    "crf": (18, 20, 23, 26, 28, 30, 32, 34),
    "lossy": (0, 20, 40, 60, 80, 100, 140, 200),
}
# crf and lossy are the odd ones out: a HIGHER value is the smaller file.
_ASCENDING = {"crf", "lossy"}


def ladder_for(knob: str, current: float) -> tuple[int, ...]:
    """The values ``knob`` may still take, best-first, starting below current."""
    if knob == "width":
        values = []
        value = int(current)
        while value > MIN_WIDTH:
            value = max(MIN_WIDTH, int(value * _WIDTH_STEP))
            values.append(value)
        return tuple(values)
    ladder = _LADDERS.get(knob, ())
    if knob in _ASCENDING:
        return tuple(value for value in ladder if value > current)
    return tuple(value for value in ladder if value < current)


def size_factor(knob: str, old: float, new: float) -> float:
    """Predicted size multiplier from moving ``knob`` from ``old`` to ``new``."""
    if knob == "width":
        return (new / old) ** 2  # area, and height follows width
    if knob == "fps":
        return new / old  # one frame each
    if knob == "colors":
        # Sub-linear: a GIF's per-pixel cost is the palette's bit depth.
        return math.log2(max(new, 2)) / math.log2(max(old, 2))
    if knob == "crf":
        return 2 ** (-(new - old) / 6)  # x264's rule of thumb: +6 crf, half the bits
    if knob == "lossy":
        return 0.5 ** ((new - old) / 60)  # measured on animated clips: --lossy=60 halves
    return 1.0


def step_down(
    settings: dict[str, Any], fit: Iterable[str], overshoot: float, *, floor: bool
) -> dict[str, Any] | None:
    """Lower fit knobs enough to cover ``overshoot``; return None if none can move.

    ``floor`` takes every knob to the bottom of its ladder - the last attempt,
    where there is nothing to save for.
    """
    changed = dict(settings)
    needed = 1 / overshoot
    for knob in fit:
        if knob not in changed:
            continue  # no starting value, so nothing to trade
        current = float(changed[knob])
        ladder = ladder_for(knob, current)
        if not ladder:
            continue
        if floor:
            changed[knob] = ladder[-1]
            continue
        for value in ladder:
            changed[knob] = value
            if _achieved(settings, changed, fit) <= needed:
                return changed
    if changed == settings:
        return None
    return changed


def _achieved(before: dict[str, Any], after: dict[str, Any], fit: Iterable[str]) -> float:
    factor = 1.0
    for knob in fit:
        if knob in before and knob in after:
            factor *= size_factor(knob, float(before[knob]), float(after[knob]))
    return factor
