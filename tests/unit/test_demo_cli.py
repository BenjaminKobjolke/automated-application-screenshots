"""Unit tests for the demo-run expansion (demo x language) and texts lookup."""

import json
from contextlib import contextmanager
from unittest.mock import MagicMock

import pytest

from screenshot_tool import config
from screenshot_tool import demo_cli as demo_cli_module
from screenshot_tool.demo_cli import DemoCLI, _run_label

MULTI_LANG = {
    "process_name": "python.exe",
    "title_substring": "FastCalculator",
    "output_dir": "screenshots/calc",
    "launch": {"command": ["app", "--automation-demo", "{demo_id}"], "cwd": None},
    "demos": [
        {"id": 1, "name": "basic-math", "languages": ["en", "de"]},
        {"id": 2, "name": "minimal"},
    ],
}


def load(tmp_path):
    path = tmp_path / "app.json"
    path.write_text(json.dumps(MULTI_LANG), encoding="utf-8")
    config.load_config(path)


def test_run_expands_demos_by_language(tmp_path, monkeypatch):
    load(tmp_path)
    calls: list[tuple[int, str | None]] = []
    monkeypatch.setattr(
        DemoCLI,
        "_run_demo",
        lambda self, demo, language=None: calls.append((demo.id, language)) or True,
    )
    assert DemoCLI().run("all") == 0
    assert calls == [(1, "en"), (1, "de"), (2, None)]


def test_run_single_demo_covers_all_its_languages(tmp_path, monkeypatch):
    load(tmp_path)
    calls: list[tuple[int, str | None]] = []
    monkeypatch.setattr(
        DemoCLI,
        "_run_demo",
        lambda self, demo, language=None: calls.append((demo.id, language)) or True,
    )
    assert DemoCLI().run("1") == 0
    assert calls == [(1, "en"), (1, "de")]


def test_demo_dispatch_runs_inside_configured_fancyzones_pause(tmp_path, monkeypatch):
    load(tmp_path)
    events = []

    @contextmanager
    def pause(enabled):
        events.append(("enter", enabled))
        try:
            yield
        finally:
            events.append(("exit", enabled))

    monkeypatch.setattr(demo_cli_module.fancyzones, "paused", pause)
    monkeypatch.setattr(
        demo_cli_module,
        "run_all",
        lambda demos, run_demo: events.append(("dispatch",)) or 0,
    )

    assert DemoCLI().run("all") == 0
    assert events == [("enter", True), ("dispatch",), ("exit", True)]


def test_pause_exits_when_demo_raises(tmp_path, monkeypatch):
    load(tmp_path)
    pause = MagicMock()
    monkeypatch.setattr(demo_cli_module.fancyzones, "paused", pause)

    def fail(*args):
        raise RuntimeError("demo failed")

    monkeypatch.setattr(DemoCLI, "_run_demo", fail)
    with pytest.raises(RuntimeError, match="demo failed"):
        DemoCLI().run("all")
    pause.return_value.__enter__.assert_called_once()
    pause.return_value.__exit__.assert_called_once()


@pytest.mark.parametrize(
    "selector, config_data",
    [
        ("bad", MULTI_LANG),
        (
            "all",
            {
                "process_name": "python.exe",
                "title_substring": "FastCalculator",
                "output_dir": "screenshots/calc",
                "launch": {"command": ["app"], "cwd": None},
            },
        ),
    ],
)
def test_invalid_or_empty_demo_selection_does_not_pause(tmp_path, monkeypatch, selector, config_data):
    path = tmp_path / "app.json"
    path.write_text(json.dumps(config_data), encoding="utf-8")
    config.load_config(path)
    pause = MagicMock()
    monkeypatch.setattr(demo_cli_module.fancyzones, "paused", pause)

    assert DemoCLI().run(selector) == 1
    pause.assert_not_called()


def test_run_label_with_and_without_language(tmp_path):
    load(tmp_path)
    demo = config.settings.demos[0]
    assert _run_label(demo, "de") == "basic-math [de]"
    assert _run_label(demo, None) == "basic-math"


def test_run_demo_fails_before_launch_when_texts_file_missing(tmp_path, monkeypatch):
    data = {**MULTI_LANG, "texts_dir": str(tmp_path / "texts")}
    path = tmp_path / "app.json"
    path.write_text(json.dumps(data), encoding="utf-8")
    config.load_config(path)

    def _no_launch(*args, **kwargs):
        raise AssertionError("app must not be launched when the texts file is missing")

    monkeypatch.setattr(demo_cli_module.subprocess, "Popen", _no_launch)
    assert DemoCLI()._run_demo(config.settings.demos[0], "de") is False
