"""Wait for direct media pages to decode and paint their requested video frame."""

import math
import time

from playwright.sync_api import Page

VIDEO_FRAME_TIMEOUT_MS = 30000
MEDIA_TIME_KEY = "t"
NPT_PREFIX = "npt:"
VIDEO_TIME_TOLERANCE_SECONDS = 0.1

_VIDEO_FRAME_READY_JS = (
    "() => { const v = document.querySelector('video'); "
    "return !!v && v.readyState >= 2 && !v.seeking && v.videoWidth > 0; }"
)
_VIDEO_METADATA_READY_JS = (
    "() => { const v = document.querySelector('video'); "
    "return !!v && v.readyState >= 1 && Number.isFinite(v.duration); }"
)
_SEEK_TO_TARGET_JS = (
    "(target) => { const v = document.querySelector('video'); "
    f"const tolerance = {VIDEO_TIME_TOLERANCE_SECONDS}; "
    "const goal = Math.min(target, v.duration); "
    "if (!v.seeking && v.currentTime < goal - tolerance) v.currentTime = goal; }"
)
_VIDEO_TARGET_READY_JS = (
    "(target) => { const v = document.querySelector('video'); "
    f"const tolerance = {VIDEO_TIME_TOLERANCE_SECONDS}; "
    "return !!v && v.readyState >= 2 && !v.seeking && v.videoWidth > 0 && "
    "v.currentTime >= Math.min(target, v.duration) - tolerance; }"
)
_PAINT_JS = "() => new Promise((resolve) => requestAnimationFrame(() => requestAnimationFrame(resolve)))"


def media_start_seconds(fragment: str) -> float | None:
    """Return the start time from a media fragment, if it is supported."""
    for component in fragment.split("&"):
        key, separator, value = component.partition("=")
        if separator and key == MEDIA_TIME_KEY:
            if value.startswith(NPT_PREFIX):
                value = value[len(NPT_PREFIX) :]
            value = value.split(",", 1)[0]
            parts = value.split(":")
            if not 1 <= len(parts) <= 3 or any(not part for part in parts):
                return None
            try:
                values = [float(part) for part in parts]
            except ValueError:
                return None
            if any(not math.isfinite(part) or part < 0 for part in values):
                return None
            if len(values) == 1:
                return values[0]
            if len(values) == 2:
                return values[0] * 60 + values[1]
            return values[0] * 3600 + values[1] * 60 + values[2]
    return None


def _remaining_timeout_ms(deadline: float) -> int:
    return max(1, math.ceil((deadline - time.monotonic()) * 1000))


def wait_for_video_frame(page: Page, fragment: str = "") -> None:
    """Wait for a decoded, painted frame; raises Playwright TimeoutError on timeout."""
    target = media_start_seconds(fragment)
    if target is None:
        page.wait_for_function(_VIDEO_FRAME_READY_JS, timeout=VIDEO_FRAME_TIMEOUT_MS)
        page.evaluate(_PAINT_JS)
        return

    deadline = time.monotonic() + VIDEO_FRAME_TIMEOUT_MS / 1000
    page.wait_for_function(
        _VIDEO_METADATA_READY_JS,
        timeout=_remaining_timeout_ms(deadline),
    )
    _remaining_timeout_ms(deadline)
    page.evaluate(_SEEK_TO_TARGET_JS, target)
    page.wait_for_function(
        _VIDEO_TARGET_READY_JS,
        arg=target,
        timeout=_remaining_timeout_ms(deadline),
    )
    page.wait_for_function(
        _PAINT_JS,
        timeout=_remaining_timeout_ms(deadline),
    )
