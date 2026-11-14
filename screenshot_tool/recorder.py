"""Record window frames and save requested, uploaded or single-capture stills.

Stills requested via ``request_still`` are saved from the next captured frame,
or from an optional target window captured at that frame tick. Uploaded stills
bypass desktop capture, while single-capture stills capture once without starting
the thread. Stills honour the configured crop, maximum output size and optional
minimum saved-image size.
"""

import threading
import time
from io import BytesIO
from pathlib import Path

from PIL import Image

from .app_logger import AppLogger
from .capture import WindowCapture
from .demo_common import save_uploaded_still
from .image_fit import fit_png_within, fit_within, size_shortfall

_FRAME_WARN_THRESHOLD = 1000


class Recorder(threading.Thread):
    """Captures a window region at a fixed fps until stopped."""

    def __init__(
        self,
        hwnd: int,
        fps: int,
        stills_dir: Path,
        crop: tuple[int, int, int, int] = (0, 0, 0, 0),
        max_size: tuple[int, int] | None = None,
        min_size: tuple[int, int] | None = None,
    ) -> None:
        super().__init__(daemon=True)
        self.hwnd = hwnd
        self.fps = fps
        self.stills_dir = stills_dir
        self.crop = crop  # (top, right, bottom, left) px removed from each frame
        self.max_size = max_size
        self.min_size = min_size
        self.frames: list[tuple[float, Image.Image]] = []
        self.saved_stills: list[str] = []
        self.size_errors: list[str] = []
        self._pending_stills: list[tuple[str, int | None]] = []
        self._lock = threading.Lock()
        self._stop = threading.Event()
        self._warned = False

    def request_still(self, name: str, hwnd: int | None = None) -> None:
        """Save a frame from the next tick as ``<stills_dir>/<name>.png``."""
        with self._lock:
            self._pending_stills.append((name, hwnd))

    def save_uploaded_still(self, name: str, png: bytes) -> None:
        """Save PNG bytes supplied by the application as a named still."""
        if self.max_size is not None:
            try:
                png = fit_png_within(png, self.max_size)
            except (OSError, ValueError) as error:
                AppLogger.warning(
                    f"Could not scale uploaded still '{name}'; saving original bytes: {error}"
                )
        save_uploaded_still(self.stills_dir, name, png)
        self.saved_stills.append(name)
        if self.min_size is not None:
            try:
                with Image.open(BytesIO(png)) as image:
                    self._check_size(name, image.size)
            except (OSError, ValueError) as error:
                message = f"Could not verify size of still '{name}': {error}"
                AppLogger.error(message)
                self.size_errors.append(message)

    def capture_still(self, name: str, hwnd: int | None = None) -> bool:
        """Capture and save one window still without starting the recorder."""
        try:
            target_hwnd = self.hwnd if hwnd is None else hwnd
            image = self._fit(self._capture_cropped_window(target_hwnd))
            WindowCapture.save_screenshot(image, self.stills_dir / f"{name}.png")
            self.saved_stills.append(name)
            AppLogger.info(f"Saved still '{name}'")
            return self._check_size(name, image.size)
        except Exception as e:
            AppLogger.error(f"Still capture failed for '{name}': {e}")
            return False

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
            image = self._apply_crop(image)
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

    def _apply_crop(self, image: Image.Image) -> Image.Image:
        """Remove the configured (top, right, bottom, left) inset from a frame."""
        top, right, bottom, left = self.crop
        if not (top or right or bottom or left):
            return image
        w, h = image.size
        box = (left, top, w - right, h - bottom)
        if box[2] <= box[0] or box[3] <= box[1]:
            return image  # inset larger than the frame; ignore rather than crash
        return image.crop(box)

    def _capture_cropped_window(self, hwnd: int) -> Image.Image:
        """Capture one window and apply the recorder's configured crop."""
        return self._apply_crop(WindowCapture.capture_window(hwnd))

    def _fit(self, image: Image.Image) -> Image.Image:
        """Shrink a still to the configured limit when one is set."""
        return fit_within(image, self.max_size) if self.max_size is not None else image

    def _check_size(self, name: str, size: tuple[int, int]) -> bool:
        """Log and remember a saved still that misses the configured size floor."""
        if self.min_size is None:
            return True
        error = size_shortfall(f"Still '{name}'", size, self.min_size)
        if error is None:
            return True
        AppLogger.error(error)
        self.size_errors.append(error)
        return False

    def _save_pending_stills(self, image: Image.Image) -> None:
        with self._lock:
            pending, self._pending_stills = self._pending_stills, []
        for name, hwnd in pending:
            path = self.stills_dir / f"{name}.png"
            still = image
            if hwnd is not None and hwnd != self.hwnd:
                try:
                    still = self._capture_cropped_window(hwnd)
                except Exception as e:
                    AppLogger.error(f"Still capture failed for '{name}' (hwnd {hwnd}): {e}")
                    continue
            fitted = self._fit(still)
            WindowCapture.save_screenshot(fitted, path)
            self.saved_stills.append(name)
            AppLogger.info(f"Saved still '{name}'")
            self._check_size(name, fitted.size)
