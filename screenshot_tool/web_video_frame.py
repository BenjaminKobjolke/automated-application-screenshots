"""Wait for direct media pages to decode and paint their first video frame."""

from playwright.sync_api import Page

VIDEO_FRAME_TIMEOUT_MS = 30000

_VIDEO_FRAME_READY_JS = (
    "() => { const v = document.querySelector('video'); "
    "return !!v && v.readyState >= 2 && !v.seeking && v.videoWidth > 0; }"
)
_PAINT_JS = "() => new Promise((resolve) => requestAnimationFrame(() => requestAnimationFrame(resolve)))"


def wait_for_video_frame(page: Page) -> None:
    """Wait for a decoded, painted frame; raises Playwright TimeoutError on timeout."""
    page.wait_for_function(_VIDEO_FRAME_READY_JS, timeout=VIDEO_FRAME_TIMEOUT_MS)
    page.evaluate(_PAINT_JS)
