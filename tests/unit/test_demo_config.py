"""Unit tests for the demo/launch sections of the config schema."""

import json

import pytest
from demo_config_data import DEMO_ONLY, LANGUAGE_ONLY, WITH_APP_SETTINGS, write_config

from screenshot_tool import config


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


def test_demo_languages_parsed(tmp_path):
    data = json.loads(json.dumps(DEMO_ONLY))
    data["demos"][0]["languages"] = ["en", "de"]
    settings = config.load_config(write_config(tmp_path, data))
    assert settings.demos[0].languages == ("en", "de")


def test_demo_languages_default_empty(tmp_path):
    settings = config.load_config(write_config(tmp_path, DEMO_ONLY))
    assert settings.demos[0].languages == ()


@pytest.mark.parametrize("bad", ["en", [1], [""], [None]])
def test_demo_languages_must_be_string_list(tmp_path, bad):
    data = json.loads(json.dumps(DEMO_ONLY))
    data["demos"][0]["languages"] = bad
    with pytest.raises(SystemExit, match="languages"):
        config.load_config(write_config(tmp_path, data))




def test_texts_dir_parsed(tmp_path):
    settings = config.load_config(write_config(tmp_path, {**DEMO_ONLY, "texts_dir": "texts"}))
    assert settings.texts_dir == "texts"


def test_texts_dir_default_none(tmp_path):
    settings = config.load_config(write_config(tmp_path, DEMO_ONLY))
    assert settings.texts_dir is None


def test_texts_dir_must_be_string(tmp_path):
    with pytest.raises(SystemExit, match="texts_dir"):
        config.load_config(write_config(tmp_path, {**DEMO_ONLY, "texts_dir": 5}))








def test_app_settings_must_be_object(tmp_path):
    data = json.loads(json.dumps(DEMO_ONLY))
    data["demos"][0]["app_settings"] = ["not", "a", "dict"]
    with pytest.raises(SystemExit, match="app_settings"):
        config.load_config(write_config(tmp_path, data))








