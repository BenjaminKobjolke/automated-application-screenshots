"""Tests for the start and end idle alerts around CLI runs."""

import json
import sys
from pathlib import Path

import pytest

from screenshot_tool.demo_cli import DemoCLI
from screenshot_tool.main import main


def _write_config(tmp_path: Path) -> Path:
    data = {
        "process_name": "app.exe",
        "title_substring": "App",
        "output_dir": str(tmp_path / "configured"),
        "pause_fancyzones": False,
        "launch": {"command": ["app.exe"], "cwd": None},
        "demos": [{"id": 1, "name": "overview", "formats": ["gif", "mp4"]}],
    }
    path = tmp_path / "app.json"
    path.write_text(json.dumps(data), encoding="utf-8")
    return path


@pytest.mark.parametrize(("warned", "expected_calls"), [(True, 1), (False, 0)])
def test_main_shows_end_alert_only_when_start_warning_was_shown(
    tmp_path, monkeypatch, warned, expected_calls
):
    config_path = _write_config(tmp_path)
    notified = []
    monkeypatch.setattr("screenshot_tool.main.setup_utf8_console", lambda: None)
    monkeypatch.setattr(sys, "argv", ["screenshot-tool", "--config", str(config_path), "--demo", "1"])
    monkeypatch.setattr("screenshot_tool.main.idle_guard.close_leftover_alerts", lambda: None)
    monkeypatch.setattr("screenshot_tool.main.idle_guard.warn_if_active", lambda: warned)
    monkeypatch.setattr(
        "screenshot_tool.main.idle_guard.notify_done", lambda: notified.append(True)
    )
    monkeypatch.setattr(DemoCLI, "_run_demo", lambda *_args, **_kwargs: True)

    assert main() == 0
    assert len(notified) == expected_calls


def test_main_shows_end_alert_when_run_raises(tmp_path, monkeypatch):
    config_path = _write_config(tmp_path)
    notified = []
    monkeypatch.setattr("screenshot_tool.main.setup_utf8_console", lambda: None)
    monkeypatch.setattr(sys, "argv", ["screenshot-tool", "--config", str(config_path), "--demo", "1"])
    monkeypatch.setattr("screenshot_tool.main.idle_guard.close_leftover_alerts", lambda: None)
    monkeypatch.setattr("screenshot_tool.main.idle_guard.warn_if_active", lambda: True)
    monkeypatch.setattr(
        "screenshot_tool.main.idle_guard.notify_done", lambda: notified.append(True)
    )

    def fail_demo(*_args, **_kwargs):
        raise RuntimeError()

    monkeypatch.setattr(DemoCLI, "_run_demo", fail_demo)

    with pytest.raises(RuntimeError):
        main()

    assert notified == [True]


def test_main_skips_both_idle_alerts_when_requested(tmp_path, monkeypatch):
    calls = []
    config_path = _write_config(tmp_path)
    monkeypatch.setattr("screenshot_tool.main.setup_utf8_console", lambda: None)
    monkeypatch.setattr(
        sys,
        "argv",
        ["screenshot-tool", "--skip-idle-check", "--config", str(config_path), "--demo", "1"],
    )
    monkeypatch.setattr("screenshot_tool.main.idle_guard.close_leftover_alerts", lambda: None)
    monkeypatch.setattr(
        "screenshot_tool.main.idle_guard.warn_if_active", lambda: calls.append("start")
    )
    monkeypatch.setattr(
        "screenshot_tool.main.idle_guard.notify_done", lambda: calls.append("done")
    )
    monkeypatch.setattr(DemoCLI, "_run_demo", lambda *_args, **_kwargs: True)

    assert main() == 0
    assert calls == []


@pytest.mark.parametrize("skip_idle_check", [False, True])
def test_main_closes_leftover_alerts_before_start_warning(
    tmp_path, monkeypatch, skip_idle_check
):
    config_path = _write_config(tmp_path)
    order = []
    argv = ["screenshot-tool", "--config", str(config_path), "--demo", "1"]
    if skip_idle_check:
        argv.insert(1, "--skip-idle-check")
    monkeypatch.setattr("screenshot_tool.main.setup_utf8_console", lambda: None)
    monkeypatch.setattr(sys, "argv", argv)
    monkeypatch.setattr(
        "screenshot_tool.main.idle_guard.close_leftover_alerts",
        lambda: order.append("close"),
    )
    monkeypatch.setattr(
        "screenshot_tool.main.idle_guard.warn_if_active",
        lambda: order.append("warn") or False,
    )
    monkeypatch.setattr(DemoCLI, "_run_demo", lambda *_args, **_kwargs: True)

    assert main() == 0
    assert order == (["close"] if skip_idle_check else ["close", "warn"])


def test_main_does_not_close_leftover_alerts_for_list_mode(tmp_path, monkeypatch):
    config_path = _write_config(tmp_path)
    calls = []
    monkeypatch.setattr("screenshot_tool.main.setup_utf8_console", lambda: None)
    monkeypatch.setattr(
        sys, "argv", ["screenshot-tool", "--config", str(config_path), "--list"]
    )
    monkeypatch.setattr(
        "screenshot_tool.main.idle_guard.close_leftover_alerts",
        lambda: calls.append("close"),
    )
    monkeypatch.setattr("screenshot_tool.main.list_config", lambda: None)

    assert main() == 0
    assert calls == []
