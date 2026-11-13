"""Cross-process detached live sessions with a fake Android SDK."""

from __future__ import annotations

import json
import socket
import subprocess
import sys
import time
from pathlib import Path

import psutil
import pytest
from android_fake_helpers import install_fake_android

ROOT = Path(__file__).parents[2]
FAKE_DAEMON = ROOT / "tests" / "fixtures" / "fake_flutter_daemon.py"


def _available_port() -> int:
    with socket.socket() as listener:
        listener.bind(("127.0.0.1", 0))
        return int(listener.getsockname()[1])


def _config(tmp_path: Path, *, flutter: list[str] | None = None) -> Path:
    config = tmp_path / "config.json"
    config.write_text(
        json.dumps(
            {
                "output_dir": "output",
                "live": {
                    "target": "android_emulator",
                    "avd": "Fake_AVD",
                    "devices": {"tablet": "Fake_Tablet"},
                    "port": _available_port(),
                    "flutter": flutter or [sys.executable, str(FAKE_DAEMON)],
                    "project_dir": str(tmp_path),
                    "app_settings": {"demo_account_token": "owner"},
                    "start_timeout": 10,
                },
            }
        ),
        encoding="utf-8",
    )
    return config


def _call(*args: str, timeout: int = 120) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [sys.executable, "-m", "screenshot_tool.main", *args],
        cwd=ROOT,
        capture_output=True,
        text=True,
        timeout=timeout,
    )


def _start(config: Path, folder: Path, *extra: str) -> dict[str, object]:
    result = _call("--config", str(config), "--live-start", str(folder), *extra)
    assert result.returncode == 0, result.stdout + result.stderr
    return json.loads(result.stdout)


def _send(folder: Path, command: dict[str, object]) -> dict[str, object]:
    result = _call("--live-send", str(folder), json.dumps(command))
    assert result.returncode == 0, result.stdout + result.stderr
    return json.loads(result.stdout)


def _stop(folder: Path) -> subprocess.CompletedProcess[str]:
    return _call("--live-stop", str(folder))


def _running(state: Path) -> list[Path]:
    running = state / "running"
    return sorted(running.iterdir()) if running.exists() else []


def _wait_for_process_exit(pid: int) -> bool:
    deadline = time.monotonic() + 10
    while time.monotonic() < deadline:
        if not psutil.pid_exists(pid):
            return True
        time.sleep(0.1)
    return not psutil.pid_exists(pid)


def test_android_cold_start_commands_reset_and_stop(tmp_path, monkeypatch):
    state = install_fake_android(tmp_path, monkeypatch)
    reset_log = tmp_path / "resets.jsonl"
    monkeypatch.setenv("FLUTTER_FAKE_CONTROL", str(tmp_path / "control"))
    monkeypatch.setenv("FLUTTER_FAKE_RESETS", str(reset_log))
    config = _config(tmp_path)
    folder = tmp_path / "session"
    shot = tmp_path / "current.png"

    start = _start(config, folder)
    assert start["device"] == "emulator-5554"
    assert "start Fake_AVD emulator-5554" in (state / "calls.log").read_text()
    session = json.loads((folder / "live-session.json").read_text())
    pid = session["pid"]
    try:
        for command in (
            {"command": "read_text"},
            {"command": "tap_text", "text": "Open details"},
            {"command": "tap_key", "key": "details_button"},
            {"command": "type_text", "text": "Ada"},
            {"command": "press_key", "key": "enter"},
        ):
            assert _send(folder, command)["ok"] is True
        assert _send(folder, {"command": "shot", "out": str(shot)})["ok"] is True
        assert shot.exists()
        assert _send(
            folder,
            {"command": "reset", "app_settings": {"demo_account_token": "recipient"}},
        )["ok"] is True
        assert json.loads(reset_log.read_text().splitlines()[-1]) == {
            "demo_account_token": "recipient"
        }
        assert _send(folder, {"command": "reset"})["ok"] is True
        assert json.loads(reset_log.read_text().splitlines()[-1]) == {
            "demo_account_token": "recipient"
        }
    finally:
        stopped = _stop(folder)

    assert stopped.returncode == 0, stopped.stdout + stopped.stderr
    assert "kill emulator-5554" in (state / "calls.log").read_text()
    assert _running(state) == []
    assert not (folder / "live-session.json").exists()
    assert _wait_for_process_exit(pid)


def test_android_reuses_matching_running_emulator(tmp_path, monkeypatch):
    state = install_fake_android(tmp_path, monkeypatch)
    (state / "running").mkdir()
    (state / "running" / "emulator-5556").write_text("Fake_AVD", encoding="utf-8")
    monkeypatch.setenv("FLUTTER_FAKE_CONTROL", str(tmp_path / "control"))
    config = _config(tmp_path)
    folder = tmp_path / "session"

    try:
        start = _start(config, folder)
    finally:
        stopped = _stop(folder)

    assert start["device"] == "emulator-5556"
    assert stopped.returncode == 0
    assert "start " not in (state / "calls.log").read_text()
    assert "kill " not in (state / "calls.log").read_text()
    assert _running(state) == [state / "running" / "emulator-5556"]


def test_android_device_override_starts_requested_avd_and_stops_only_it(tmp_path, monkeypatch):
    state = install_fake_android(tmp_path, monkeypatch)
    (state / "running").mkdir()
    (state / "running" / "emulator-5554").write_text("Other_AVD", encoding="utf-8")
    monkeypatch.setenv("FLUTTER_FAKE_CONTROL", str(tmp_path / "control"))
    config = _config(tmp_path)
    folder = tmp_path / "session"

    try:
        start = _start(config, folder, "--live-device", "tablet")
    finally:
        stopped = _stop(folder)

    assert start["device"] == "emulator-5556"
    assert stopped.returncode == 0
    assert "start Fake_Tablet emulator-5556" in (state / "calls.log").read_text()
    assert "kill emulator-5556" in (state / "calls.log").read_text()
    assert (state / "running" / "emulator-5554").read_text() == "Other_AVD"


def test_android_failed_start_cleans_up_owned_emulator(tmp_path, monkeypatch):
    state = install_fake_android(tmp_path, monkeypatch)
    monkeypatch.setenv("FLUTTER_FAKE_CONTROL", str(tmp_path / "control"))
    config = _config(tmp_path, flutter=[sys.executable, "-c", "import sys; sys.exit(1)"])
    folder = tmp_path / "session"

    try:
        result = _call("--config", str(config), "--live-start", str(folder))
    finally:
        stopped = _stop(folder)

    assert stopped.returncode == 0, stopped.stdout + stopped.stderr
    assert result.returncode == 1
    assert json.loads(result.stdout)["ok"] is False
    assert "kill emulator-5554" in (state / "calls.log").read_text()
    assert _running(state) == []
    assert not (folder / "live-session.json").exists()
    assert not any(
        process.info["cmdline"]
        and "-m" in process.info["cmdline"]
        and "screenshot_tool.live_detached" in process.info["cmdline"]
        and "--serve" in process.info["cmdline"]
        for process in psutil.process_iter(["cmdline"])
    )
