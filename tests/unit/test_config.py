"""Unit tests for config loading and Settings derivation."""

import json

import pytest

from screenshot_tool import config


def write_config(tmp_path, data):
    path = tmp_path / "app.json"
    path.write_text(json.dumps(data), encoding="utf-8")
    return path


VALID = {
    "process_name": "app.exe",
    "title_substring": "My App",
    "dropdown_relative_pos": [100, 200],
    "output_dir": "screenshots",
    "screenshot_filename": "main.png",
    "delay_after_change": 1.5,
    "languages": {"de": "Deutsch", "en": "English", "fr": "Français"},
}


def test_load_valid_config(tmp_path):
    settings = config.load_config(write_config(tmp_path, VALID))
    assert settings.process_name == "app.exe"
    assert settings.dropdown_relative_pos == (100, 200)
    assert settings.delay_after_change == 1.5


def test_language_codes_sorted_and_reverse_mapping(tmp_path):
    settings = config.load_config(write_config(tmp_path, VALID))
    assert settings.language_codes == ["de", "en", "fr"]
    assert settings.name_to_code == {"Deutsch": "de", "English": "en", "Français": "fr"}


def test_missing_file_exits(tmp_path):
    with pytest.raises(SystemExit, match="not found"):
        config.load_config(tmp_path / "nope.json")


def test_invalid_json_exits(tmp_path):
    path = tmp_path / "bad.json"
    path.write_text("{not json", encoding="utf-8")
    with pytest.raises(SystemExit, match="Invalid JSON"):
        config.load_config(path)


def test_missing_keys_exits(tmp_path):
    data = dict(VALID)
    del data["languages"]
    del data["output_dir"]
    with pytest.raises(SystemExit, match="missing keys"):
        config.load_config(write_config(tmp_path, data))


def test_load_config_rebinds_module_settings(tmp_path):
    original = config.settings
    try:
        loaded = config.load_config(write_config(tmp_path, VALID))
        assert config.settings is loaded
    finally:
        config.settings = original
