"""Unit tests for the network (mobile) demo mode of the config schema."""

import json

import pytest

from screenshot_tool import config

NETWORK = {
    "output_dir": "screenshots/app",
    "network": {"port": 8765},
    "demos": [
        {"id": 1, "name": "overview", "formats": ["gif", "mp4"], "pixel_ratio": 2.0},
        {
            "id": 2,
            "name": "settings",
            "formats": ["png"],
            "steps": [
                {"type": "tap", "key": "settings_button"},
                {"type": "screenshot", "name": "s"},
            ],
        },
    ],
}


def write(tmp_path, data):
    path = tmp_path / "app.json"
    path.write_text(json.dumps(data), encoding="utf-8")
    return path


def test_network_config_needs_no_process_name(tmp_path):
    settings = config.load_config(write(tmp_path, NETWORK))
    assert settings.network is not None and settings.network.port == 8765
    assert settings.launch is None
    assert settings.process_name == ""


def test_demo_fields_pixel_ratio_steps_and_wants_video(tmp_path):
    settings = config.load_config(write(tmp_path, NETWORK))
    overview, stills = settings.demos
    assert overview.pixel_ratio == 2.0 and overview.wants_video
    assert stills.pixel_ratio == 1.0 and not stills.wants_video
    assert stills.steps[0] == {"type": "tap", "key": "settings_button"}


def test_launch_and_network_are_exclusive(tmp_path):
    data = {**NETWORK, "launch": {"command": ["app"]}}
    with pytest.raises(SystemExit, match="launch"):
        config.load_config(write(tmp_path, data))


def test_demos_without_launch_or_network_fail(tmp_path):
    data = {k: v for k, v in NETWORK.items() if k != "network"}
    with pytest.raises(SystemExit, match="launch"):
        config.load_config(write(tmp_path, data))


def test_steps_must_be_objects_with_a_type(tmp_path):
    data = json.loads(json.dumps(NETWORK))
    data["demos"][1]["steps"] = [{"key": "x"}]
    with pytest.raises(SystemExit, match="steps"):
        config.load_config(write(tmp_path, data))


def test_launch_mode_still_requires_process_name(tmp_path):
    data = {"output_dir": "x", "launch": {"command": ["app"]}, "demos": [{"id": 1, "name": "a"}]}
    with pytest.raises(SystemExit, match="process_name"):
        config.load_config(write(tmp_path, data))
