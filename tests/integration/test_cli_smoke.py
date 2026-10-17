"""Integration smoke test: run the real CLI end-to-end in --list mode."""

import json
import os
import socket
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


def _free_port() -> int:
    with socket.socket() as listener:
        listener.bind(("127.0.0.1", 0))
        return int(listener.getsockname()[1])


def test_live_subprocess_keeps_stdout_json_and_routes_logs_to_stderr(tmp_path):
    port = _free_port()
    fake_flutter = Path(__file__).parents[1] / "fixtures" / "fake_flutter_daemon.py"
    screenshot = tmp_path / "home.png"
    config_path = tmp_path / "live.json"
    config_path.write_text(
        json.dumps(
            {
                "output_dir": "output",
                "live": {
                    "target": "windows",
                    "port": port,
                    "flutter": [sys.executable, str(fake_flutter)],
                    "project_dir": str(tmp_path),
                    "start_timeout": 10,
                },
            }
        ),
        encoding="utf-8",
    )
    commands = [
        {"command": "start", "id": 1},
        {"command": "screens", "id": 2},
        {"command": "shot", "screen": "home", "out": str(screenshot), "id": 3},
        {"command": "reload", "id": 4},
        {"command": "stop", "id": 5},
    ]
    env = os.environ.copy()
    env["FLUTTER_FAKE_CONTROL"] = str(tmp_path / "control")

    result = subprocess.run(
        [
            sys.executable,
            "-m",
            "screenshot_tool.main",
            "--config",
            str(config_path),
            "--live",
            "--target",
            "windows",
        ],
        cwd=PROJECT_ROOT,
        input="\n".join(json.dumps(command) for command in commands) + "\n",
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        timeout=60,
        env=env,
    )

    assert result.returncode == 0, result.stderr
    responses = [json.loads(line) for line in result.stdout.splitlines()]
    assert [response["id"] for response in responses] == [1, 2, 3, 4, 5]
    assert all(response["ok"] for response in responses), responses
    assert responses[1]["screens"] == [{"name": "home"}]
    assert responses[3]["command"] == "reload"
    assert responses[3]["result"] == "reloaded"
    assert screenshot.read_bytes() == b"fake-png"
    assert "Starting live screenshot session" in result.stderr


def test_live_requires_config_section_and_rejects_incompatible_flags(tmp_path):
    config_path = tmp_path / "without-live.json"
    config_path.write_text(json.dumps({"output_dir": "output"}), encoding="utf-8")

    missing = subprocess.run(
        [sys.executable, "-m", "screenshot_tool.main", "--config", str(config_path), "--live"],
        cwd=PROJECT_ROOT,
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        timeout=30,
    )
    incompatible = subprocess.run(
        [sys.executable, "-m", "screenshot_tool.main", "--live", "--list"],
        cwd=PROJECT_ROOT,
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        timeout=30,
    )

    assert missing.returncode != 0
    assert "requires a config with a live section" in missing.stderr
    assert incompatible.returncode != 0
    assert "--live cannot be combined with" in incompatible.stderr
