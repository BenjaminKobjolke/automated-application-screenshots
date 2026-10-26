"""Run configured web demos through the browser and WebSocket connector."""

from __future__ import annotations

import re
import shutil
import subprocess
import tempfile
import time
from pathlib import Path

from playwright.sync_api import Error as PlaywrightError
from playwright.sync_api import Page

from .app_logger import AppLogger
from .compose.gif import clip_to_gif
from .compose.video import cut_to_mp4
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
from .network_demo_cli import GIF_NAME, VIDEO_NAME
from .web_browser import WebBrowser, build_demo_url
from .web_config import WebSettings
from .web_socket_server import WebDemoServer

TAIL_S = 0.5
SCREENSHOT_NAME_PATTERN = re.compile(r"[A-Za-z0-9][A-Za-z0-9_-]{0,127}\Z")


class WebDemoCLI:
    """Capture stills and browser video for demos on one web application."""

    def __init__(self, web: WebSettings) -> None:
        self._web = web
        self._browser: WebBrowser | None = None

    def run(self, demos: tuple[DemoSpec, ...]) -> int:
        """Run all selected demos in one browser process."""
        try:
            with WebBrowser(self._web) as browser:
                self._browser = browser
                return run_all(demos, self._run_demo)
        except (PlaywrightError, OSError) as error:
            AppLogger.error(f"Unable to run web demos: {error}")
            return 1

    def _run_demo(self, demo: DemoSpec, language: str | None) -> bool:
        out_dir = output_dir_for(demo, language)
        AppLogger.info(f"\n--- Demo {demo.id} '{_run_label(demo, language)}' ---")
        try:
            texts = load_texts(demo, language)
        except FileNotFoundError as error:
            AppLogger.error(str(error))
            return False

        out_dir.mkdir(parents=True, exist_ok=True)
        _clear_stale_stills(out_dir)
        width, height = (demo.width, demo.height) if demo.width is not None else self._web.viewport
        video_dir = (
            Path(tempfile.mkdtemp(prefix="screenshot-tool-web-video-"))
            if demo.wants_video
            else None
        )
        server = WebDemoServer(self._web.origin)
        context = None
        page: Page | None = None
        video = None
        opened_at = time.monotonic()
        started_at: float | None = None
        ended_at: float | None = None
        event_ok = False
        try:
            assert self._browser is not None
            context = self._browser.create_context(
                viewport=(width, height), locale=language, record_video_dir=video_dir
            )
            page = context.new_page()
            video = page.video
            server.set_start(
                {
                    "command": "start",
                    "demo": demo.id,
                    "language": language,
                    "settings": dict(demo.app_settings),
                    "texts": texts,
                    "steps": list(demo.steps),
                }
            )
            page.goto(
                build_demo_url(self._web, demo, server.port, language),
                wait_until="domcontentloaded",
                timeout=int(ACCEPT_TIMEOUT_S * 1000),
            )
            event_ok, started_at, ended_at = self._event_loop(page, server, out_dir)
            if event_ok:
                page.wait_for_timeout(int(TAIL_S * 1000))
        except (PlaywrightError, OSError, TimeoutError) as error:
            AppLogger.error(f"Web demo failed: {error}")
        finally:
            try:
                if context is not None:
                    context.close()
            finally:
                server.close()

        video_ok = True
        try:
            if demo.wants_video:
                if video is None:
                    AppLogger.error("Browser did not produce a video recording.")
                    video_ok = False
                else:
                    source = Path(video.path())
                    if source.is_file() and source.stat().st_size:
                        start = max(0.0, (started_at or opened_at) - opened_at)
                        end = max(start + 0.05, (ended_at or time.monotonic()) - opened_at)
                        if ended_at is not None:
                            end += TAIL_S
                        cut_to_mp4(source, start, end, demo.fps, out_dir / VIDEO_NAME)
                        if "gif" in demo.formats:
                            clip_to_gif(
                                out_dir / VIDEO_NAME,
                                {"fps": demo.fps, "width": width},
                                out_dir / GIF_NAME,
                            )
                    else:
                        AppLogger.error("Browser did not produce a video recording.")
                        video_ok = False
        except (
            OSError,
            PlaywrightError,
            RuntimeError,
            ValueError,
            subprocess.SubprocessError,
        ) as error:
            AppLogger.error(f"Unable to export web demo video: {error}")
            video_ok = False
        finally:
            if video_dir is not None:
                shutil.rmtree(video_dir, ignore_errors=True)
        return event_ok and video_ok and _run_verify(demo, language)

    @staticmethod
    def _event_loop(
        page: Page, server: WebDemoServer, out_dir: Path
    ) -> tuple[bool, float | None, float | None]:
        """Poll connector events while servicing Playwright's routed requests."""
        opened_at = time.monotonic()
        connection_deadline = opened_at + ACCEPT_TIMEOUT_S
        cap = opened_at + DEMO_CAP_S
        last_event = opened_at
        started_at: float | None = None
        ended_at: float | None = None
        while True:
            now = time.monotonic()
            waiting_for_connection = not server.connected and started_at is None
            if waiting_for_connection and now > connection_deadline:
                AppLogger.error(f"Web connector did not connect within {ACCEPT_TIMEOUT_S:.0f}s.")
                return False, started_at, ended_at
            if now > cap:
                AppLogger.error(f"Demo exceeded {DEMO_CAP_S:.0f}s cap; aborting.")
                return False, started_at, ended_at
            if now - last_event > EVENT_TIMEOUT_S:
                AppLogger.error(f"No demo event for {EVENT_TIMEOUT_S:.0f}s; aborting.")
                return False, started_at, ended_at
            event = server.poll()
            if event is None:
                page.wait_for_timeout(100)
                continue
            last_event = time.monotonic()
            if event.event == "demo_started":
                started_at = last_event
                AppLogger.info(f"Demo {event.demo} started.")
            elif event.event == "screenshot" and event.name:
                if SCREENSHOT_NAME_PATTERN.fullmatch(event.name) is None:
                    AppLogger.error(
                        "Web connector requested a screenshot with an invalid name."
                    )
                    return False, started_at, ended_at
                still = out_dir / f"{event.name}.png"
                page.screenshot(path=str(still))
                server.send({"command": "screenshot_done", "name": event.name})
                AppLogger.info(f"  {still}")
            elif event.event == "error":
                AppLogger.error(f"Web connector reported: {event.message}")
                return False, started_at, ended_at
            elif event.event == "demo_ended":
                ended_at = last_event
                AppLogger.info("Demo ended.")
                return True, started_at, ended_at

