"""Background thread recording a window as timestamped frames.

Stills requested via ``request_still`` are saved from the next captured frame,
so they are always consistent with the recording (and full quality — the
capture is already lossless).
"""

import threading
import time
from pathlib import Path

from PIL import Image

from .app_logger import AppLogger
from .capture import WindowCapture

_FRAME_WARN_THRESHOLD = 1000


class Recorder(threading.Thread):
    """Captures a window region at a fixed fps until stopped."""

    def __init__(self, hwnd: int, fps: int, stills_dir: Path) -> None:
        super().__init__(daemon=True)
        self.hwnd = hwnd
        self.fps = fps
        self.stills_dir = stills_dir
        self.frames: list[tuple[float, Image.Image]] = []
        self.saved_stills: list[str] = []
        self._pending_stills: list[str] = []
        self._lock = threading.Lock()
        self._stop = threading.Event()
        self._warned = False

    def request_still(self, name: str) -> None:
        """Save the next captured frame as ``<stills_dir>/<name>.png``."""
        with self._lock:
            self._pending_stills.append(name)

    def stop(self) -> None:
        self._stop.set()

    def run(self) -> None:
        interval = 1.0 / self.fps
        next_tick = time.perf_counter()
        while not self._stop.is_set():
            try:
                image = WindowCapture.capture_window(self.hwnd)
            except Exception as e:
                AppLogger.error(f"Frame capture failed, stopping recording: {e}")
                return
            self.frames.append((time.perf_counter(), image))
            self._save_pending_stills(image)
            if len(self.frames) > _FRAME_WARN_THRESHOLD and not self._warned:
                self._warned = True
                AppLogger.info(
                    f"Recording exceeds {_FRAME_WARN_THRESHOLD} frames; memory use is growing"
                )
            next_tick += interval
            delay = next_tick - time.perf_counter()
            if delay > 0:
                time.sleep(delay)
            else:
                # Capture slower than fps: skip missed ticks instead of drifting
                next_tick = time.perf_counter()

    def _save_pending_stills(self, image: Image.Image) -> None:
        with self._lock:
            pending, self._pending_stills = self._pending_stills, []
        for name in pending:
            path = self.stills_dir / f"{name}.png"
            WindowCapture.save_screenshot(image, path)
            self.saved_stills.append(name)
            AppLogger.info(f"Saved still '{name}'")
