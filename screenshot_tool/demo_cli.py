"""Demo recording orchestration: launch app, record window, export GIF/MP4.

Flow per demo: start event server -> launch the app with the demo id and
server port -> find its window -> record frames from ``demo_started`` to
``demo_ended`` (saving stills on ``screenshot`` events) -> export.
"""

import subprocess
import tempfile
import time
from pathlib import Path

import psutil

from . import config
from .app_logger import AppLogger
from .config import DemoSpec, build_launch_command, write_app_settings_file
from .demo_server import DemoServer
from .exporter import export_gif, export_mp4
from .recorder import Recorder
from .window_finder import WindowFinder

WINDOW_TIMEOUT_S = 30.0
ACCEPT_TIMEOUT_S = 30.0
EVENT_TIMEOUT_S = 60.0
DEMO_CAP_S = 300.0
TAIL_S = 0.5
EXIT_GRACE_S = 10.0


class DemoCLI:
    """Runs the demos of the loaded config and reports a summary."""

    def run(self, selector: str) -> int:
        """Run one demo (by id) or all of them.

        Args:
            selector: A demo id like "1", or "all".

        Returns:
            Exit code (0 when every selected demo succeeded).
        """
        settings = config.settings
        if not settings.demos:
            AppLogger.error("Config has no 'demos' section - nothing to record.")
            return 1

        if selector == "all":
            demos = settings.demos
        else:
            try:
                demo_id = int(selector)
            except ValueError:
                AppLogger.error(f"--demo expects a demo id or 'all', got '{selector}'")
                return 1
            demos = tuple(d for d in settings.demos if d.id == demo_id)
            if not demos:
                available = ", ".join(str(d.id) for d in settings.demos)
                AppLogger.error(f"No demo with id {demo_id} (available: {available})")
                return 1

        failed = [demo.name for demo in demos if not self._run_demo(demo)]
        AppLogger.info(f"\n{'=' * 50}")
        AppLogger.info(f"Demos complete: {len(demos) - len(failed)}/{len(demos)} succeeded")
        for name in failed:
            AppLogger.info(f"  FAILED: {name}")
        return 0 if not failed else 1

    def _run_demo(self, demo: DemoSpec) -> bool:
        launch = config.settings.launch
        assert launch is not None  # config validation guarantees this
        out_dir = Path(config.settings.output_dir) / "demos" / demo.name
        AppLogger.info(f"\n--- Demo {demo.id} '{demo.name}' ---")

        server = DemoServer()
        settings_file = write_app_settings_file(demo, Path(tempfile.gettempdir()))
        cmd = build_launch_command(launch, demo, server.port, settings_file)
        AppLogger.info(f"Launching: {' '.join(cmd)}")
        proc = subprocess.Popen(cmd, cwd=launch.cwd)
        recorder: Recorder | None = None
        try:
            if not self._accept_connection(server, proc):
                return False

            # The app reports its own native window handle in demo_started -
            # no window-finding heuristics, no ambiguity
            hwnd = self._wait_for_started_hwnd(server, proc)
            if hwnd is None:
                return False
            AppLogger.info(f"Recording window '{WindowFinder.get_window_title(hwnd)}'")
            WindowFinder.bring_to_foreground(hwnd)
            time.sleep(0.3)

            recorder = Recorder(hwnd, demo.fps, stills_dir=out_dir)
            recorder.start()
            ok = self._event_loop(server, proc, recorder)

            if recorder.is_alive():
                time.sleep(TAIL_S)  # keep the final state in the recording
            recorder.stop()
            recorder.join(timeout=5)
            # Export even after an abnormal end - partial recordings help debugging
            self._export(demo, recorder, out_dir)
            return ok and bool(recorder.frames)
        finally:
            server.close()
            self._shutdown(proc)
            if settings_file is not None:
                settings_file.unlink(missing_ok=True)

    @staticmethod
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

    @staticmethod
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

    @staticmethod
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

    @staticmethod
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

    @staticmethod
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
