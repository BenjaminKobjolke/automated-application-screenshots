"""Shared demo configuration data for demo config tests."""

import json

LANGUAGE_ONLY = {
    "process_name": "app.exe",
    "title_substring": "My App",
    "dropdown_relative_pos": [100, 200],
    "output_dir": "screenshots",
    "screenshot_filename": "main.png",
    "delay_after_change": 1.5,
    "languages": {"de": "Deutsch", "en": "English"},
}

DEMO_ONLY = {
    "process_name": "python.exe",
    "title_substring": "FastCalculator",
    "output_dir": "screenshots/calc",
    "launch": {
        "command": [
            "uv",
            "run",
            "python",
            "main.py",
            "--automation-demo",
            "{demo_id}",
            "--automation-demo-port",
            "{port}",
        ],
        "cwd": "D:/somewhere",
    },
    "demos": [
        {
            "id": 1,
            "name": "basic-math",
            "fps": 12,
            "formats": ["gif", "mp4"],
            "width": 640,
            "height": 420,
        },
        {"id": 2, "name": "minimal"},
    ],
}

WITH_APP_SETTINGS = {
    **DEMO_ONLY,
    "demos": [
        {
            "id": 1,
            "name": "big-font",
            "app_settings": {"editor/font_point_size": 18, "window/theme": "dark"},
        }
    ],
}


def write_config(tmp_path, data):
    path = tmp_path / "app.json"
    path.write_text(json.dumps(data), encoding="utf-8")
    return path
