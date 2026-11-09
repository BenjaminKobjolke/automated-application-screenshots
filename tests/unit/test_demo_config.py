"""Unit tests for the demo/launch sections of the config schema."""

import json

import pytest
from demo_config_data import DEMO_ONLY, LANGUAGE_ONLY, write_config

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
    assert all(not demo.scale_to_window_size for demo in settings.demos)
    assert all(demo.max_output_size is None for demo in settings.demos)


def test_top_level_scale_default_applies_with_per_demo_override(tmp_path):
    data = json.loads(json.dumps(DEMO_ONLY))
    data["scale_to_window_size"] = True
    for demo in data["demos"]:
        demo["width"] = 640
        demo["height"] = 420
    data["demos"][1]["scale_to_window_size"] = False

    settings = config.load_config(write_config(tmp_path, data))

    assert settings.demos[0].scale_to_window_size is True
    assert settings.demos[0].max_output_size == (640, 420)
    assert settings.demos[1].scale_to_window_size is False
    assert settings.demos[1].max_output_size is None


def test_per_demo_scale_flag_enables_output_size(tmp_path):
    data = json.loads(json.dumps(DEMO_ONLY))
    data["demos"][0]["scale_to_window_size"] = True

    settings = config.load_config(write_config(tmp_path, data))

    assert settings.demos[0].scale_to_window_size is True
    assert settings.demos[0].max_output_size == (640, 420)


@pytest.mark.parametrize("location", ["top-level", "per-demo"])
def test_scale_flag_must_be_boolean(tmp_path, location):
    data = json.loads(json.dumps(DEMO_ONLY))
    if location == "top-level":
        data["scale_to_window_size"] = "true"
    else:
        data["demos"][0]["scale_to_window_size"] = "true"

    with pytest.raises(SystemExit, match="scale_to_window_size"):
        config.load_config(write_config(tmp_path, data))


def test_scaled_launch_demo_requires_width_and_height(tmp_path):
    data = json.loads(json.dumps(DEMO_ONLY))
    data["demos"][1]["scale_to_window_size"] = True

    with pytest.raises(SystemExit, match=r"scale_to_window_size.*minimal"):
        config.load_config(write_config(tmp_path, data))


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








