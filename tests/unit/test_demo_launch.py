"""Launch command and app settings config tests."""

import json

from demo_config_data import DEMO_ONLY, WITH_APP_SETTINGS, write_config

from screenshot_tool import config


def test_build_launch_command_appends_language(tmp_path):
    settings = config.load_config(write_config(tmp_path, DEMO_ONLY))
    assert settings.launch is not None
    cmd = config.build_launch_command(
        settings.launch, settings.demos[0], port=1234, settings_file=None, language="de"
    )
    assert cmd[-2:] == ["--automation-demo-language", "de"]

def test_build_launch_command_appends_texts_file(tmp_path):
    settings = config.load_config(write_config(tmp_path, DEMO_ONLY))
    assert settings.launch is not None
    texts_file = tmp_path / "de.json"
    cmd = config.build_launch_command(
        settings.launch,
        settings.demos[0],
        port=1234,
        settings_file=None,
        language="de",
        texts_file=texts_file,
    )
    assert cmd[-2:] == ["--automation-demo-texts", str(texts_file)]

def test_app_settings_parsed_and_coerced_to_str(tmp_path):
    settings = config.load_config(write_config(tmp_path, WITH_APP_SETTINGS))
    assert settings.demos[0].app_settings == (
        ("editor/font_point_size", "18"),
        ("window/theme", "dark"),
    )

def test_app_settings_default_empty(tmp_path):
    settings = config.load_config(write_config(tmp_path, DEMO_ONLY))
    assert settings.demos[0].app_settings == ()

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
