"""Network demo mode: a phone/emulator app connects, records itself, uploads.

Per run: send ``start`` (demo id, whether to record video, settings, language,
texts, optional steps) -> receive ``demo_started`` / inline ``screenshot``
stills / ``demo_ended`` -> if video was wanted, receive the ``video`` header
and the mp4 bytes -> derive the GIF on this side. Output lands where launch
mode puts it, so ``compose`` needs no changes.
"""

import time
from pathlib import Path

from .app_logger import AppLogger
from .compose.gif import clip_to_gif
from .config import DemoSpec
from .demo_common import (
    ACCEPT_TIMEOUT_S,
    DEMO_CAP_S,
    EVENT_TIMEOUT_S,
    _clear_stale_stills,
    _run_label,
    _run_verify,
    load_texts,
    output_dir_for,
    run_all,
)
from .demo_server import DemoServer

VIDEO_NAME = "demo.mp4"
GIF_NAME = "demo.gif"


class NetworkDemoCLI:
    """Runs demos against one app connection held open for the whole batch."""

    def __init__(
        self, server: DemoServer, accept_timeout: float = ACCEPT_TIMEOUT_S
    ) -> None:
        self._server = server
        self._accept_timeout = accept_timeout

    def run(self, demos: tuple[DemoSpec, ...]) -> int:
        """Wait for the app once, then run every selected demo over that link.

        Returns:
            Exit code (0 when every run succeeded).
        """
        AppLogger.info(
            f"Listening on port {self._server.port} for {self._accept_timeout:.0f}s; "
            f"start the app with "
            f"--dart-define=AUTOMATION_HOST=<this pc ip>:{self._server.port}"
        )
        try:
            if not self._server.accept(timeout=self._accept_timeout):
                AppLogger.error("App never connected to the demo port.")
                return 1
            AppLogger.info("App connected.")
            return run_all(demos, self._run_demo)
        finally:
            self._server.close()

    def _run_demo(self, demo: DemoSpec, language: str | None) -> bool:
        out_dir = output_dir_for(demo, language)
        AppLogger.info(f"\n--- Demo {demo.id} '{_run_label(demo, language)}' ---")
        try:
            texts = load_texts(demo, language)
        except FileNotFoundError as e:
            AppLogger.error(str(e))
            return False
        out_dir.mkdir(parents=True, exist_ok=True)
        _clear_stale_stills(out_dir)

        try:
            self._server.send(
                {
                    "command": "start",
                    "demo": demo.id,
                    "video": demo.wants_video,
                    "pixel_ratio": demo.pixel_ratio,
                    "settings": dict(demo.app_settings),
                    "language": language,
                    "texts": texts,
                    "steps": list(demo.steps),
                }
            )
            if demo.wants_video:
                AppLogger.info("Waiting for the app (accept the recording prompt on the phone)...")
            ok = self._event_loop(out_dir)
            if ok and demo.wants_video:
                ok = self._receive_video(out_dir)
        except (ConnectionError, TimeoutError) as e:
            AppLogger.error(str(e) or f"No data from the app for {EVENT_TIMEOUT_S:.0f}s")
            return False
        if ok and "gif" in demo.formats:
            clip_to_gif(out_dir / VIDEO_NAME, {"fps": demo.fps}, out_dir / GIF_NAME)
            AppLogger.info(f"  {out_dir / GIF_NAME}")
        return ok and _run_verify(demo, language)

    def _event_loop(self, out_dir: Path) -> bool:
        """Handle events until demo_ended; True on a clean end."""
        cap = time.monotonic() + DEMO_CAP_S
        last_event = time.monotonic()
        while True:
            now = time.monotonic()
            if now > cap:
                AppLogger.error(f"Demo exceeded {DEMO_CAP_S:.0f}s cap; aborting.")
                return False
            if now - last_event > EVENT_TIMEOUT_S:
                AppLogger.error(f"No demo event for {EVENT_TIMEOUT_S:.0f}s; aborting.")
                return False
            event = self._server.next_event(timeout=1.0)
            if event is None:
                continue
            last_event = time.monotonic()
            if event.event == "demo_started":
                AppLogger.info(f"Demo {event.demo} started.")
            elif event.event == "screenshot" and event.name and event.png is not None:
                (out_dir / f"{event.name}.png").write_bytes(event.png)
                AppLogger.info(f"  {out_dir / f'{event.name}.png'}")
            elif event.event == "error":
                AppLogger.error(f"App reported: {event.message}")
                return False
            elif event.event == "demo_ended":
                AppLogger.info("Demo ended.")
                return True

    def _receive_video(self, out_dir: Path) -> bool:
        """Wait for the ``video`` header, then pull exactly that many bytes."""
        deadline = time.monotonic() + EVENT_TIMEOUT_S
        while time.monotonic() < deadline:
            event = self._server.next_event(timeout=1.0)
            if event is None:
                continue
            if event.event == "error":
                AppLogger.error(f"App reported: {event.message}")
                return False
            if event.event == "video" and event.size:
                AppLogger.info(f"Receiving {event.size} bytes of video...")
                (out_dir / VIDEO_NAME).write_bytes(
                    self._server.read_exact(event.size, timeout=EVENT_TIMEOUT_S)
                )
                AppLogger.info(f"  {out_dir / VIDEO_NAME}")
                return True
        AppLogger.error("Timed out waiting for the video upload.")
        return False
