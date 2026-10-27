"""Encode artifacts to a size budget and select the best attempt.

A config states the budget ("max_size": "2MB") and which knobs the search may
move ("fit": ["colors", "fps"]); everything it does not list is a constraint.
The search runs at most three encodes, so it steps as far down a knob's ladder
as the overshoot suggests rather than one rung at a time.

The predictions are rough on purpose - the loop measures and corrects, and a
better model would buy nothing for three attempts.
"""

from __future__ import annotations

import shutil
import tempfile
from collections.abc import Callable, Iterable
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from ..app_logger import AppLogger
from .fit_ladder import step_down

# Three encodes: enough to converge from a wild first guess, few enough that a
# GIF pass stays seconds rather than minutes.
MAX_ATTEMPTS = 3


@dataclass(frozen=True)
class Attempt:
    """One encode: what it was told, and what came out."""

    settings: dict[str, Any]
    size: int
    path: Path


Encoder = Callable[[dict[str, Any], Path], None]


def format_size(size: int) -> str:
    return f"{size / 1000 / 1000:.2f}MB" if size >= 1000 * 1000 else f"{size / 1000:.0f}KB"


def _best(attempts: list[Attempt], max_bytes: int | None) -> Attempt:
    """The best quality that fits; the smallest file when nothing does."""
    if max_bytes is None:
        return attempts[0]
    fitting = [a for a in attempts if a.size <= max_bytes]
    if fitting:
        return max(fitting, key=lambda a: a.size)
    return min(attempts, key=lambda a: a.size)


def _describe(settings: dict[str, Any], fit: Iterable[str]) -> str:
    shown = [f"{k}={settings[k]}" for k in fit if k in settings]
    return ", ".join(shown) if shown else "default settings"


def encode_to_budget(
    encode: Encoder,
    settings: dict[str, Any],
    output: Path,
    *,
    max_bytes: int | None = None,
    fit: Iterable[str] = (),
    on_miss: str = "warn",
    label: str | None = None,
) -> Attempt:
    """Encode ``settings`` to ``output``, degrading until it fits ``max_bytes``.

    Args:
        encode: Called as ``encode(settings, path)``; writes one file.
        settings: The encoder settings the config asked for - always attempt 1.
        output: Where the winning attempt ends up.
        max_bytes: Size budget, or None to encode once and keep it.
        fit: Knobs the search may move, in the order it should spend them.
        on_miss: "warn" keeps the closest attempt; "error" raises instead.
        label: Name used in the log lines (defaults to the output file name).

    Returns:
        The attempt that was kept.

    Raises:
        RuntimeError: The budget was missed and ``on_miss`` is "error".
    """
    name = label or output.name
    fit = tuple(fit)
    output.parent.mkdir(parents=True, exist_ok=True)
    attempts: list[Attempt] = []
    current = dict(settings)

    with tempfile.TemporaryDirectory() as work:
        for attempt in range(MAX_ATTEMPTS):
            candidate = Path(work) / f"attempt{attempt}{output.suffix}"
            encode(current, candidate)
            size = candidate.stat().st_size
            attempts.append(Attempt(dict(current), size, candidate))
            if max_bytes is None:
                break
            AppLogger.info(
                f"  {name}: {format_size(size)} "
                f"(budget {format_size(max_bytes)}) [{_describe(current, fit)}]"
            )
            if size <= max_bytes or attempt == MAX_ATTEMPTS - 1:
                break
            # Second-to-last try goes straight to the bottom: there is no
            # attempt left to correct a cautious step.
            nxt = step_down(
                current, fit, size / max_bytes, floor=attempt == MAX_ATTEMPTS - 2
            )
            if nxt is None:
                AppLogger.info(f"  {name}: nothing left to trade; keeping the best attempt")
                break
            current = nxt

        best = _best(attempts, max_bytes)
        shutil.move(str(best.path), str(output))

    missed = max_bytes is not None and best.size > max_bytes
    if missed:
        message = (
            f"{name} is {format_size(best.size)}, over the {format_size(max_bytes or 0)} "
            f"budget after {len(attempts)} attempt(s) ({_describe(best.settings, fit)}); "
            f"loosen a constraint or raise max_size"
        )
        if on_miss == "error":
            raise RuntimeError(message)
        AppLogger.warning(f"WARNING: {message}")
    return best
