"""Tests for output and stills-only overrides in demo CLI runs."""

import json
import sys
from pathlib import Path

import pytest

from screenshot_tool import config
from screenshot_tool.demo_cli import DemoCLI
from screenshot_tool.demo_common import output_dir_for
from screenshot_tool.main import main


def _write_config(tmp_path: Path) -> Path:
    data = {
        "process_name": "app.exe",
        "title_substring": "App",
        "output_dir": str(tmp_path / "configured"),
        "pause_fancyzones": False,
        "launch": {"command": ["app.exe"], "cwd": None},
        "demos": [
            {"id": 1, "name": "overview", "formats": ["gif", "mp4"]},
        ],
    }
    path = tmp_path / "app.json"
    path.write_text(json.dumps(data), encoding="utf-8")
    return path


def _run_main(monkeypatch, *arguments: str) -> int:
    monkeypatch.setattr("screenshot_tool.main.setup_utf8_console", lambda: None)
    monkeypatch.setattr(
        sys, "argv", ["screenshot-tool", *arguments, "--skip-idle-check"]
    )
    return main()


def test_output_override_applies_to_demo_recording(tmp_path, monkeypatch):
    config_path = _write_config(tmp_path)
    custom_output = tmp_path / "custom"

    def record_still(self, demo, language=None):
        still_path = output_dir_for(demo, language) / "x.png"
        still_path.parent.mkdir(parents=True, exist_ok=True)
        still_path.write_bytes(b"png")
        return True

    monkeypatch.setattr(DemoCLI, "_run_demo", record_still)

    assert _run_main(
        monkeypatch,
        "--config",
        str(config_path),
        "--output",
        str(custom_output),
        "--demo",
        "1",
    ) == 0

    assert (custom_output / "demos" / "overview" / "x.png").is_file()
    assert not (tmp_path / "configured").exists()


@pytest.mark.parametrize("include_demo", [False, True])
def test_output_override_applies_to_compose(tmp_path, monkeypatch, include_demo):
    config_path = _write_config(tmp_path)
    custom_output = tmp_path / "custom"
    seen = {}

    monkeypatch.setattr(DemoCLI, "_run_demo", lambda self, demo, language=None: True)

    def compose(selector):
        seen["output_dir"] = config.settings.output_dir
        return 0

    monkeypatch.setattr(
        "screenshot_tool.compose.run",
        compose,
    )

    arguments = ["--config", str(config_path), "--output", str(custom_output)]
    if include_demo:
        arguments.extend(["--demo", "1"])
    arguments.append("--compose")

    assert _run_main(monkeypatch, *arguments) == 0
    assert seen["output_dir"] == str(custom_output.resolve())


def test_stills_only_replaces_demo_formats(tmp_path, monkeypatch):
    config_path = _write_config(tmp_path)
    seen = {}

    def record_stills(self, demo, language=None):
        seen["formats"] = demo.formats
        seen["wants_video"] = demo.wants_video
        return True

    monkeypatch.setattr(DemoCLI, "_run_demo", record_stills)

    assert _run_main(
        monkeypatch,
        "--config",
        str(config_path),
        "--stills-only",
        "--demo",
        "1",
    ) == 0
    assert seen == {"formats": ("png",), "wants_video": False}


@pytest.mark.parametrize(
    "arguments",
    [
        ("--stills-only",),
        ("--stills-only", "--demo", "1", "--compose"),
    ],
)
def test_stills_only_rejects_invalid_combinations(tmp_path, monkeypatch, arguments):
    config_path = _write_config(tmp_path)

    with pytest.raises(SystemExit) as error:
        _run_main(monkeypatch, "--config", str(config_path), *arguments)

    assert error.value.code == 2
