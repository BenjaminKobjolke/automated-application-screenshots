"""Shared configuration data for compose tests."""

import json

from screenshot_tool import config

BASE = {
    "process_name": "python.exe",
    "title_substring": "fman",
    "output_dir": "media",
    "launch": {"command": ["run.bat", "{demo_id}", "{port}"]},
    "demos": [
        {"id": 1, "name": "themes", "formats": []},
        {"id": 3, "name": "tour-a", "group": "tour", "caption": "Two panes"},
        {"id": 4, "name": "tour-b", "group": "tour", "captions": {"de": "Zwei"}},
        {"id": 8, "name": "feature-goto", "group": "feature"},
    ],
}


def with_compose(*steps):
    return {**BASE, "compose": list(steps)}


def write_config(tmp_path, data):
    path = tmp_path / "app.json"
    path.write_text(json.dumps(data), encoding="utf-8")
    return path


def load(tmp_path, data):
    return config.load_config(write_config(tmp_path, data))
