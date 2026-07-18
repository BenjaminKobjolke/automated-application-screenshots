"""Integration smoke test: run the real CLI end-to-end in --list mode."""

import subprocess
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).parent.parent.parent


def test_list_languages_runs_end_to_end():
    result = subprocess.run(
        [sys.executable, "-m", "screenshot_tool.main", "--list"],
        cwd=PROJECT_ROOT,
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        timeout=60,
    )
    assert result.returncode == 0, result.stderr
    assert "Total:" in result.stdout
