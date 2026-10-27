"""Helpers for the desktop demo recording lifecycle."""

import subprocess
import time
from pathlib import Path

import psutil

from .app_logger import AppLogger
from .config import DemoSpec
from .demo_common import ACCEPT_TIMEOUT_S, DEMO_CAP_S, EVENT_TIMEOUT_S
from .demo_server import DemoServer
from .exporter import export_gif, export_mp4
from .recorder import Recorder
from .window_finder import WindowFinder

WINDOW_TIMEOUT_S = 30.0
EXIT_GRACE_S = 10.0


def _wait_for_started_hwnd(server: DemoServer, proc: subprocess.Popen) -> int | None:
    """Wait for demo_started and return the window handle it reports."""
    deadline = time.monotonic() + WINDOW_TIMEOUT_S
    while time.monotonic() < deadline:
        if proc.poll() is not None:
            AppLogger.error("App exited before sending demo_started.")
            return None
        try:
            event = server.next_event(timeout=1.0)
        except ConnectionError as e:
            AppLogger.error(str(e))
            return None
        if event is None:
            continue
        if event.event != "demo_started":
            AppLogger.info(f"Ignoring '{event.event}' before demo_started")
            continue
        if event.hwnd is None:
            AppLogger.error(
                "demo_started carries no 'hwnd' - the app must report its window handle "
                "(see docs/AUTOMATION_INTERFACE.md)."
            )
            return None
        if not WindowFinder.is_window_valid(event.hwnd):
            AppLogger.error(f"Reported hwnd {event.hwnd} is not a valid window.")
            return None
        AppLogger.info(f"Demo {event.demo} started; window hwnd {event.hwnd}")
        return event.hwnd
    AppLogger.error("Timed out waiting for demo_started.")
    return None


def _accept_connection(server: DemoServer, proc: subprocess.Popen) -> bool:
    deadline = time.monotonic() + ACCEPT_TIMEOUT_S
    while time.monotonic() < deadline:
        if proc.poll() is not None:
            AppLogger.error("App exited before connecting to the demo port.")
            return False
        if server.accept(timeout=1.0):
            return True
    AppLogger.error("App never connected to the demo port.")
    return False


def _event_loop(server: DemoServer, proc: subprocess.Popen, recorder: Recorder) -> bool:
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
        if proc.poll() is not None:
            AppLogger.error("App exited before sending demo_ended.")
            return False
        try:
            event = server.next_event(timeout=1.0)
        except ConnectionError as e:
            AppLogger.error(str(e))
            return False
        if event is None:
            continue
        last_event = time.monotonic()
        if event.event == "screenshot" and event.name:
            recorder.request_still(event.name)
        elif event.event == "demo_ended":
            AppLogger.info("Demo ended.")
            return True


def _export(demo: DemoSpec, recorder: Recorder, out_dir: Path) -> None:
    if not recorder.frames:
        AppLogger.error("No frames captured; nothing to export.")
        return
    timestamps = [t for t, _ in recorder.frames]
    images = [img for _, img in recorder.frames]
    AppLogger.info(f"Captured {len(images)} frames; exporting {', '.join(demo.formats)}...")
    if "gif" in demo.formats:
        export_gif(images, timestamps, out_dir / "demo.gif")
        AppLogger.info(f"  {out_dir / 'demo.gif'}")
    if "mp4" in demo.formats:
        export_mp4(images, demo.fps, out_dir / "demo.mp4")
        AppLogger.info(f"  {out_dir / 'demo.mp4'}")
    for name in recorder.saved_stills:
        AppLogger.info(f"  {out_dir / f'{name}.png'}")


def _shutdown(proc: subprocess.Popen) -> None:
    try:
        proc.wait(timeout=EXIT_GRACE_S)
        return
    except subprocess.TimeoutExpired:
        AppLogger.info("App did not exit on its own; killing it.")
    try:
        for child in psutil.Process(proc.pid).children(recursive=True):
            child.kill()
    except psutil.NoSuchProcess:
        pass
    proc.kill()
