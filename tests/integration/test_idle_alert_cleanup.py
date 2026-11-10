"""Integration test for closing an alert owned by another process."""

import subprocess
import sys
import time

import pytest

from screenshot_tool.idle_guard import close_leftover_alerts


def test_close_leftover_alert_exits_alert_process():
    process = subprocess.Popen(
        [
            sys.executable,
            "-c",
            "from screenshot_tool.idle_guard import show_done_alert; show_done_alert()",
        ]
    )
    try:
        deadline = time.monotonic() + 10
        closed = 0
        while time.monotonic() < deadline and process.poll() is None:
            closed = close_leftover_alerts()
            if closed >= 1:
                break
            time.sleep(0.1)
        if closed < 1:
            pytest.skip("No interactive desktop alert appeared")

        assert process.wait(timeout=5) == 0
    finally:
        if process.poll() is None:
            process.kill()
            process.wait()
