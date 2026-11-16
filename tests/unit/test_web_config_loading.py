"""Integration of web settings with the root configuration loader."""

import json
from pathlib import Path

import pytest

from screenshot_tool.config import load_config


def write_config(tmp_path: Path, data: dict) -> Path:
    path = tmp_path / "app.json"
    path.write_text(json.dumps(data), encoding="utf-8")
    return path


def test_web_only_config_loads_pages_without_demos(tmp_path):
    settings = load_config(
        write_config(
            tmp_path,
            {
                "output_dir": "shots",
                "web": {
                    "base_url": "https://example.test",
                    "pages": [{"name": "home", "path": "/"}],
                },
            },
        )
    )

    assert settings.web is not None
    assert settings.web.pages[0].name == "home"
    assert settings.demos == ()
    assert settings.launch is None
    assert settings.network is None


def test_web_mode_conflicts_with_launch_mode(tmp_path):
    with pytest.raises(SystemExit, match="exactly one"):
        load_config(
            write_config(
                tmp_path,
                {
                    "output_dir": "shots",
                    "process_name": "app.exe",
                    "title_substring": "App",
                    "web": {"base_url": "https://example.test"},
                    "launch": {"command": ["app.exe"]},
                    "demos": [{"id": 1, "name": "home"}],
                },
            )
        )


def test_web_demo_path_defaults_to_root(tmp_path):
    settings = load_config(
        write_config(
            tmp_path,
            {
                "output_dir": "shots",
                "web": {"base_url": "https://example.test"},
                "demos": [{"id": 1, "name": "home"}],
            },
        )
    )

    assert settings.demos[0].path == "/"


def test_web_demo_path_must_start_with_slash(tmp_path):
    with pytest.raises(SystemExit, match="path"):
        load_config(
            write_config(
                tmp_path,
                {
                    "output_dir": "shots",
                    "web": {"base_url": "https://example.test"},
                    "demos": [{"id": 1, "name": "home", "path": "admin"}],
                },
            )
        )


def test_web_demo_dimensions_must_be_paired(tmp_path):
    with pytest.raises(SystemExit, match=r"width.*height|height.*width"):
        load_config(
            write_config(
                tmp_path,
                {
                    "output_dir": "shots",
                    "web": {"base_url": "https://example.test"},
                    "demos": [{"id": 1, "name": "home", "width": 900}],
                },
            )
        )
