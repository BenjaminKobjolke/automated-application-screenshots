"""Unit tests for web mode command-line dispatch."""

import json
import sys
from pathlib import Path

from screenshot_tool import config
from screenshot_tool import main as main_module
from screenshot_tool.demo_cli import DemoCLI
from screenshot_tool.main import main
from screenshot_tool.web_config import WebDevice


def _load_web_config(tmp_path: Path, *, demos: bool) -> Path:
    data = {
        "output_dir": str(tmp_path / "screenshots"),
        "web": {
            "base_url": "https://example.test/app",
            "pages": [{"name": "home", "path": "/home"}],
        },
    }
    if demos:
        data["demos"] = [{"id": 1, "name": "home"}]
    path = tmp_path / "web.json"
    path.write_text(json.dumps(data), encoding="utf-8")
    return path


def test_demo_cli_dispatches_web_demos(tmp_path, monkeypatch):
    cfg = _load_web_config(tmp_path, demos=True)
    config.load_config(cfg)
    seen = {}

    class StubWebDemoCLI:
        def __init__(self, web):
            seen["web"] = web

        def run(self, demos):
            seen["demos"] = demos
            return 0

    monkeypatch.setattr("screenshot_tool.web_demo_cli.WebDemoCLI", StubWebDemoCLI)

    assert DemoCLI().run("1") == 0
    assert seen["web"] is config.settings.web
    assert [demo.id for demo in seen["demos"]] == [1]


def test_main_dispatches_plain_web_run_and_forwards_output(tmp_path, monkeypatch):
    cfg = _load_web_config(tmp_path, demos=False)
    seen = {}

    class StubWebPagesCLI:
        def __init__(self, web, output_dir=None, device=WebDevice.DESKTOP):
            seen["web"] = web
            seen["output_dir"] = output_dir
            seen["device"] = device

        def run(self, start_from=None):
            seen["start_from"] = start_from
            return 0

    monkeypatch.setattr("screenshot_tool.web_pages_cli.WebPagesCLI", StubWebPagesCLI)
    monkeypatch.setattr("screenshot_tool.main.setup_utf8_console", lambda: None)
    monkeypatch.setattr(
        sys,
        "argv",
        ["screenshot-tool", "--config", str(cfg), "--output", str(tmp_path / "custom")],
    )

    assert main() == 0
    assert seen["web"] is config.settings.web
    assert seen["output_dir"] == tmp_path / "custom"
    assert seen["device"] is WebDevice.DESKTOP
    assert seen["start_from"] is None


def test_main_forwards_mobile_device_to_plain_web_run(tmp_path, monkeypatch):
    cfg = _load_web_config(tmp_path, demos=False)
    seen = {}

    class StubWebPagesCLI:
        def __init__(self, web, output_dir=None, device=WebDevice.DESKTOP):
            seen["device"] = device

        def run(self, start_from=None):
            return 0

    monkeypatch.setattr("screenshot_tool.web_pages_cli.WebPagesCLI", StubWebPagesCLI)
    monkeypatch.setattr("screenshot_tool.main.setup_utf8_console", lambda: None)
    monkeypatch.setattr(
        sys,
        "argv",
        ["screenshot-tool", "--config", str(cfg), "--device", "mobile"],
    )

    assert main() == 0
    assert seen["device"] is WebDevice.MOBILE


def test_main_rejects_mobile_device_with_demo(tmp_path, monkeypatch):
    cfg = _load_web_config(tmp_path, demos=True)
    monkeypatch.setattr("screenshot_tool.main.setup_utf8_console", lambda: None)
    monkeypatch.setattr(
        sys,
        "argv",
        ["screenshot-tool", "--config", str(cfg), "--device", "mobile", "--demo", "1"],
    )

    try:
        main()
    except SystemExit as error:
        assert error.code == 2
    else:
        raise AssertionError("expected argparse to reject --device mobile with --demo")


def test_main_rejects_mobile_device_without_web_config(tmp_path, monkeypatch):
    cfg = tmp_path / "launch.json"
    cfg.write_text(
        json.dumps(
            {
                "output_dir": str(tmp_path / "screenshots"),
                "process_name": "app.exe",
                "title_substring": "App",
            }
        ),
        encoding="utf-8",
    )
    monkeypatch.setattr("screenshot_tool.main.setup_utf8_console", lambda: None)
    monkeypatch.setattr(
        sys,
        "argv",
        ["screenshot-tool", "--config", str(cfg), "--device", "mobile"],
    )

    try:
        main()
    except SystemExit as error:
        assert error.code == 2
    else:
        raise AssertionError("expected argparse to reject mobile capture without web config")


def test_list_config_includes_web_pages(tmp_path, monkeypatch):
    config.load_config(_load_web_config(tmp_path, demos=False))
    messages: list[str] = []
    monkeypatch.setattr(main_module.AppLogger, "info", messages.append)

    main_module.list_config()

    assert any("Web pages:" in message for message in messages)
    assert any("home" in message and "/home" in message for message in messages)
