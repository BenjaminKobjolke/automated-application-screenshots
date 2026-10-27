"""Demo recording orchestration: launch app, record window, export GIF/MP4.

Flow per demo: start event server -> launch the app with the demo id and
server port -> find its window -> record frames from ``demo_started`` to
``demo_ended`` (saving stills on ``screenshot`` events) -> export.
"""

import subprocess
import tempfile
import time
from pathlib import Path

from . import config, desktop_demo, fancyzones
from .app_logger import AppLogger
from .config import DemoSpec
from .demo_common import (
    _clear_stale_stills,
    _run_label,
    _run_verify,
    output_dir_for,
    run_all,
    texts_file_for,
)
from .demo_launch import build_launch_command, child_env, write_app_settings_file
from .demo_server import DemoServer
from .network_demo_cli import NetworkDemoCLI
from .recorder import Recorder
from .window_finder import WindowFinder
from .window_geometry import WindowGeometry
from .window_stacking import WindowStacking

TAIL_S = 0.5

__all__ = ["DemoCLI", "_run_label"]


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

        if settings.web is not None:
            from .web_demo_cli import WebDemoCLI

            return WebDemoCLI(settings.web).run(demos)

        with fancyzones.paused(settings.pause_fancyzones):
            if settings.network is not None:
                # Phone app: it connects to us and records itself
                return NetworkDemoCLI(
                    DemoServer("0.0.0.0", settings.network.port),
                    accept_timeout=settings.network.accept_timeout,
                ).run(demos)
            return run_all(demos, self._run_demo)

    def _run_demo(self, demo: DemoSpec, language: str | None = None) -> bool:
        launch = config.settings.launch
        assert launch is not None  # config validation guarantees this
        out_dir = output_dir_for(demo, language)
        AppLogger.info(f"\n--- Demo {demo.id} '{_run_label(demo, language)}' ---")

        try:
            texts_file = texts_file_for(demo, language)
        except FileNotFoundError as e:
            AppLogger.error(str(e))
            return False

        server = DemoServer()
        settings_file = write_app_settings_file(demo, Path(tempfile.gettempdir()))
        cmd = build_launch_command(launch, demo, server.port, settings_file, language, texts_file)
        out_dir.mkdir(parents=True, exist_ok=True)
        _clear_stale_stills(out_dir)
        if launch.minimize_all:
            WindowStacking.minimize_all()
        AppLogger.info(f"Launching: {' '.join(cmd)}")
        proc = subprocess.Popen(cmd, cwd=launch.cwd, env=child_env(launch, demo, language))
        recorder: Recorder | None = None
        try:
            if not desktop_demo._accept_connection(server, proc):
                return False

            # The app reports its own native window handle in demo_started -
            # no window-finding heuristics, no ambiguity
            hwnd = desktop_demo._wait_for_started_hwnd(server, proc)
            if hwnd is None:
                return False
            AppLogger.info(f"Recording window '{WindowFinder.get_window_title(hwnd)}'")
            WindowFinder.bring_to_foreground(hwnd)
            WindowGeometry.move_into_work_area(hwnd)
            # Screen-region capture grabs whatever is drawn at the window's rect, so a
            # previous run's still-closing window (same app, same position) could bleed
            # in. Pin the target on top — SetForegroundWindow is unreliable, HWND_TOPMOST
            # via SetWindowPos is not — so it always sits above any leftover window.
            WindowStacking.set_topmost(hwnd)
            time.sleep(0.3)

            recorder = Recorder(hwnd, demo.fps, stills_dir=out_dir, crop=demo.crop)
            recorder.start()
            ok = desktop_demo._event_loop(server, proc, recorder)

            if recorder.is_alive():
                time.sleep(TAIL_S)  # keep the final state in the recording
            recorder.stop()
            recorder.join(timeout=5)
            # Export even after an abnormal end - partial recordings help debugging
            desktop_demo._export(demo, recorder, out_dir)
            return ok and bool(recorder.frames) and _run_verify(demo, language)
        finally:
            server.close()
            desktop_demo._shutdown(proc)
            if settings_file is not None:
                settings_file.unlink(missing_ok=True)
