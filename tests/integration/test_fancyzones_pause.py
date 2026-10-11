"""Exercise FancyZones process shutdown and restoration with a stand-in."""

import subprocess
import sys

import psutil

from screenshot_tool import fancyzones


def test_pause_restarts_a_stopped_process(monkeypatch):
    original = subprocess.Popen([sys.executable, "-c", "import time; time.sleep(60)"])
    restarted = []
    real_popen = fancyzones.subprocess.Popen

    def tracked_popen(*args, **kwargs):
        process = real_popen(*args, **kwargs)
        restarted.append(process)
        return process

    monkeypatch.setattr(fancyzones.subprocess, "Popen", tracked_popen)
    process = psutil.Process(original.pid)
    monkeypatch.setattr(
        fancyzones,
        "_running",
        lambda: [process] if process.is_running() and process.status() != psutil.STATUS_ZOMBIE else [],
    )

    try:
        with fancyzones.paused():
            assert not process.is_running()
        assert len(restarted) == 1
        assert restarted[0].poll() is None
        assert restarted[0].args == original.args
    finally:
        for child in [original, *restarted]:
            if child.poll() is None:
                child.terminate()
                try:
                    child.wait(timeout=5)
                except subprocess.TimeoutExpired:
                    child.kill()
                    child.wait(timeout=5)
