"""Validation and derivation for live Flutter configuration."""

import json

import pytest

from screenshot_tool.config import load_config
from screenshot_tool.live_config import LiveTarget, automation_host, device_id


def write_config(tmp_path, data):
    path = tmp_path / "app.json"
    path.write_text(json.dumps(data), encoding="utf-8")
    return path


def test_live_config_defaults_and_target(tmp_path):
    settings = load_config(
        write_config(
            tmp_path,
            {"output_dir": "shots", "live": {"target": "windows", "port": 8766}},
        )
    ).live

    assert settings is not None
    assert settings.target is LiveTarget.WINDOWS
    assert settings.avd is None
    assert settings.headless is False
    assert settings.flutter == ("flutter",)
    assert settings.run_args == ()
    assert settings.project_dir == tmp_path.resolve()
    assert settings.app_settings == {}
    assert settings.start_timeout == 600


def test_live_config_is_optional(tmp_path):
    assert load_config(write_config(tmp_path, {"output_dir": "shots"})).live is None


def test_live_only_config_resolves_project_dir_relative_to_config(tmp_path):
    settings = load_config(
        write_config(
            tmp_path,
            {
                "output_dir": "shots",
                "live": {"target": "android_emulator", "port": 8766, "project_dir": "../app"},
            },
        )
    ).live

    assert settings is not None
    assert settings.project_dir == (tmp_path.parent / "app").resolve()


@pytest.mark.parametrize("target", ["ios", "", None, 1])
def test_live_target_must_be_supported(tmp_path, target):
    with pytest.raises(SystemExit, match="live.target"):
        load_config(
            write_config(
                tmp_path,
                {"output_dir": "shots", "live": {"target": target, "port": 8766}},
            )
        )


@pytest.mark.parametrize("port", [True, "8766", 0, 65536, None])
def test_live_port_must_be_valid_integer(tmp_path, port):
    with pytest.raises(SystemExit, match="live.port"):
        load_config(
            write_config(
                tmp_path,
                {"output_dir": "shots", "live": {"target": "windows", "port": port}},
            )
        )


@pytest.mark.parametrize("value", ["flutter", [], ["flutter", 1], None])
def test_live_flutter_command_must_be_a_non_empty_string_list(tmp_path, value):
    with pytest.raises(SystemExit, match="live.flutter"):
        load_config(
            write_config(
                tmp_path,
                {
                    "output_dir": "shots",
                    "live": {"target": "windows", "port": 8766, "flutter": value},
                },
            )
        )


@pytest.mark.parametrize("value", ["flutter", ["flutter", 1], None])
def test_live_run_args_must_be_a_string_list(tmp_path, value):
    with pytest.raises(SystemExit, match="live.run_args"):
        load_config(
            write_config(
                tmp_path,
                {
                    "output_dir": "shots",
                    "live": {"target": "windows", "port": 8766, "run_args": value},
                },
            )
        )


@pytest.mark.parametrize("timeout", [True, 0, -1, "10", None])
def test_live_start_timeout_must_be_positive_non_boolean_number(tmp_path, timeout):
    with pytest.raises(SystemExit, match="live.start_timeout"):
        load_config(
            write_config(
                tmp_path,
                {
                    "output_dir": "shots",
                    "live": {"target": "windows", "port": 8766, "start_timeout": timeout},
                },
            )
        )


@pytest.mark.parametrize(
    ("target", "port", "expected"),
    [
        (LiveTarget.WINDOWS, 8766, "127.0.0.1:8766"),
        (LiveTarget.ANDROID_EMULATOR, 8766, "10.0.2.2:8766"),
    ],
)
def test_automation_host_is_derived_from_target(target, port, expected):
    assert automation_host(target, port) == expected


def test_device_id_uses_windows_or_selected_emulator():
    assert device_id(LiveTarget.WINDOWS) == "windows"
    assert device_id(LiveTarget.ANDROID_EMULATOR, "emulator-5556") == "emulator-5556"
