"""Unit tests for the demo/launch sections of the config schema."""

import json

import pytest

from screenshot_tool import config

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


def test_old_flat_config_still_loads(tmp_path):
    settings = config.load_config(write_config(tmp_path, LANGUAGE_ONLY))
    assert settings.launch is None
    assert settings.demos == ()
    assert settings.language_codes == ["de", "en"]


def test_demo_only_config_loads(tmp_path):
    settings = config.load_config(write_config(tmp_path, DEMO_ONLY))
    assert settings.language_names is None
    assert settings.launch is not None
    assert settings.launch.cwd == "D:/somewhere"
    assert settings.demos[0].id == 1
    assert settings.demos[0].name == "basic-math"
    assert settings.demos[0].fps == 12
    assert settings.demos[0].formats == ("gif", "mp4")
    assert settings.demos[0].width == 640
    assert settings.demos[0].height == 420


def test_demo_defaults(tmp_path):
    settings = config.load_config(write_config(tmp_path, DEMO_ONLY))
    minimal = settings.demos[1]
    assert minimal.fps == 10
    assert minimal.formats == ("gif",)
    assert minimal.width is None
    assert minimal.height is None


def test_combined_config_loads(tmp_path):
    data = {**LANGUAGE_ONLY, "launch": DEMO_ONLY["launch"], "demos": DEMO_ONLY["demos"]}
    settings = config.load_config(write_config(tmp_path, data))
    assert settings.language_codes == ["de", "en"]
    assert len(settings.demos) == 2


def test_demos_without_launch_exits(tmp_path):
    data = dict(DEMO_ONLY)
    del data["launch"]
    with pytest.raises(SystemExit, match="launch"):
        config.load_config(write_config(tmp_path, data))


def test_bad_format_value_exits(tmp_path):
    data = json.loads(json.dumps(DEMO_ONLY))
    data["demos"][0]["formats"] = ["avi"]
    with pytest.raises(SystemExit, match="format"):
        config.load_config(write_config(tmp_path, data))


def test_demo_missing_id_or_name_exits(tmp_path):
    data = json.loads(json.dumps(DEMO_ONLY))
    del data["demos"][0]["name"]
    with pytest.raises(SystemExit, match="name"):
        config.load_config(write_config(tmp_path, data))


def test_size_placeholder_without_size_exits(tmp_path):
    data = json.loads(json.dumps(DEMO_ONLY))
    data["launch"]["command"].extend(["--automation-demo-width", "{width}"])
    del data["demos"][0]["width"]
    with pytest.raises(SystemExit, match="width"):
        config.load_config(write_config(tmp_path, data))


def test_language_mode_missing_language_keys_exits(tmp_path):
    data = dict(LANGUAGE_ONLY)
    del data["dropdown_relative_pos"]
    with pytest.raises(SystemExit, match="missing keys"):
        config.load_config(write_config(tmp_path, data))


def test_app_settings_parsed_and_coerced_to_str(tmp_path):
    settings = config.load_config(write_config(tmp_path, WITH_APP_SETTINGS))
    assert settings.demos[0].app_settings == (
        ("editor/font_point_size", "18"),
        ("window/theme", "dark"),
    )


def test_app_settings_default_empty(tmp_path):
    settings = config.load_config(write_config(tmp_path, DEMO_ONLY))
    assert settings.demos[0].app_settings == ()


def test_app_settings_must_be_object(tmp_path):
    data = json.loads(json.dumps(DEMO_ONLY))
    data["demos"][0]["app_settings"] = ["not", "a", "dict"]
    with pytest.raises(SystemExit, match="app_settings"):
        config.load_config(write_config(tmp_path, data))


def test_build_launch_command_appends_settings_file_arg(tmp_path):
    settings = config.load_config(write_config(tmp_path, WITH_APP_SETTINGS))
    assert settings.launch is not None
    settings_file = tmp_path / "settings.json"
    cmd = config.build_launch_command(
        settings.launch, settings.demos[0], port=1234, settings_file=settings_file
    )
    assert cmd[-2:] == ["--automation-demo-settings", str(settings_file)]


def test_build_launch_command_substitutes_placeholders(tmp_path):
    settings = config.load_config(write_config(tmp_path, DEMO_ONLY))
    assert settings.launch is not None
    cmd = config.build_launch_command(
        settings.launch, settings.demos[0], port=54321, settings_file=None
    )
    assert cmd == [
        "uv",
        "run",
        "python",
        "main.py",
        "--automation-demo",
        "1",
        "--automation-demo-port",
        "54321",
    ]


def test_write_app_settings_file_writes_json_object(tmp_path):
    settings = config.load_config(write_config(tmp_path, WITH_APP_SETTINGS))
    path = config.write_app_settings_file(settings.demos[0], tmp_path)
    assert path is not None
    data = json.loads(path.read_text(encoding="utf-8"))
    assert data == {"editor/font_point_size": "18", "window/theme": "dark"}


def test_write_app_settings_file_none_without_settings(tmp_path):
    settings = config.load_config(write_config(tmp_path, DEMO_ONLY))
    assert config.write_app_settings_file(settings.demos[0], tmp_path) is None
