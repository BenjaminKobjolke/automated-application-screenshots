"""Unit tests for the child environment, verify checks and the stills wipe."""

import json
import os

import pytest

from screenshot_tool import config, demo_cli
from screenshot_tool.config import DemoSpec, LaunchSettings, VerifyCheck

BASE = {
    "process_name": "python.exe",
    "title_substring": "fman",
    "output_dir": "media",
    "launch": {"command": ["run.bat", "{demo_id}"]},
    "demos": [{"id": 1, "name": "overview"}],
}


def load(tmp_path, data):
    path = tmp_path / "app.json"
    path.write_text(json.dumps(data), encoding="utf-8")
    return config.load_config(path)


DEMO = DemoSpec(id=3, name="tour-a")


# --- the child environment -----------------------------------------------------


def test_the_tools_own_virtualenv_is_dropped(monkeypatch):
    monkeypatch.setenv("VIRTUAL_ENV", r"C:\tool\.venv")
    monkeypatch.setenv("PATH", os.pathsep.join([r"C:\tool\.venv\Scripts", r"C:\Python313"]))
    env = demo_cli._child_env(LaunchSettings(command=("x",), cwd=None), DEMO, None)
    assert env is not None
    assert "VIRTUAL_ENV" not in env
    assert env["PATH"] == r"C:\Python313"


def test_inherit_env_keeps_it(monkeypatch):
    monkeypatch.setenv("VIRTUAL_ENV", r"C:\tool\.venv")
    launch = LaunchSettings(command=("x",), cwd=None, inherit_env=True)
    assert demo_cli._child_env(launch, DEMO, None) is None  # nothing to change


def test_launch_env_expands_placeholders(monkeypatch, tmp_path):
    monkeypatch.setattr(config.tempfile, "gettempdir", lambda: str(tmp_path), raising=False)
    launch = LaunchSettings(
        command=("x",),
        cwd=None,
        env=(("APP_PROFILE", "{temp}/demo-{demo_id}-{name}"),),
    )
    env = demo_cli._child_env(launch, DEMO, None)
    assert env is not None
    assert env["APP_PROFILE"] == f"{tmp_path}/demo-3-tour-a"


def test_launch_env_expands_the_language(tmp_path):
    launch = LaunchSettings(command=("x",), cwd=None, env=(("APP_LANG", "{lang}"),))
    env = demo_cli._child_env(launch, DEMO, "de")
    assert env is not None
    assert env["APP_LANG"] == "de"


def test_launch_env_parses(tmp_path):
    data = {**BASE, "launch": {**BASE["launch"], "env": {"FMAN_DATA_DIRECTORY": "{temp}/p"}}}
    settings = load(tmp_path, data)
    assert settings.launch is not None
    assert settings.launch.env == (("FMAN_DATA_DIRECTORY", "{temp}/p"),)
    assert settings.launch.minimize_all is True
    assert settings.launch.inherit_env is False


def test_minimize_all_can_be_turned_off(tmp_path):
    data = {**BASE, "launch": {**BASE["launch"], "minimize_all": False}}
    settings = load(tmp_path, data)
    assert settings.launch is not None
    assert settings.launch.minimize_all is False


def test_launch_env_must_be_an_object(tmp_path):
    data = {**BASE, "launch": {**BASE["launch"], "env": ["NAME=value"]}}
    with pytest.raises(SystemExit, match="launch.env must be an object"):
        load(tmp_path, data)


# --- stale stills --------------------------------------------------------------


def test_stale_stills_are_cleared_but_videos_are_not(tmp_path):
    (tmp_path / "gone-theme.png").write_bytes(b"png")
    (tmp_path / "demo.mp4").write_bytes(b"mp4")
    demo_cli._clear_stale_stills(tmp_path)
    assert not (tmp_path / "gone-theme.png").exists()
    assert (tmp_path / "demo.mp4").exists()


# --- verify --------------------------------------------------------------------


def test_verify_passes_when_the_side_effect_landed(tmp_path):
    target = tmp_path / "settings.json"
    target.write_text('{"video_viewer_volume": 40}', encoding="utf-8")
    demo = DemoSpec(
        id=6,
        name="tour-d",
        verify=(
            VerifyCheck("exists", str(target)),
            VerifyCheck("contains", str(target), "video_viewer_volume"),
        ),
    )
    assert demo_cli._run_verify(demo, None) is True


def test_verify_fails_on_a_missing_file(tmp_path, caplog):
    demo = DemoSpec(id=6, name="d", verify=(VerifyCheck("exists", str(tmp_path / "nope")),))
    assert demo_cli._run_verify(demo, None) is False
    assert "no such file" in caplog.text


def test_verify_fails_when_the_text_is_absent(tmp_path, caplog):
    target = tmp_path / "settings.json"
    target.write_text("{}", encoding="utf-8")
    demo = DemoSpec(id=6, name="d", verify=(VerifyCheck("contains", str(target), "volume"),))
    assert demo_cli._run_verify(demo, None) is False
    assert "Verify failed" in caplog.text


def test_no_checks_is_a_pass(tmp_path):
    assert demo_cli._run_verify(DemoSpec(id=1, name="d"), None) is True


def test_verify_paths_expand_placeholders(tmp_path, monkeypatch):
    monkeypatch.setattr(config.tempfile, "gettempdir", lambda: str(tmp_path), raising=False)
    (tmp_path / "demo-6.log").write_text("done", encoding="utf-8")
    demo = DemoSpec(id=6, name="d", verify=(VerifyCheck("exists", "{temp}/demo-{demo_id}.log"),))
    assert demo_cli._run_verify(demo, None) is True


def test_verify_config_parsing(tmp_path):
    data = {
        **BASE,
        "demos": [
            {
                "id": 1,
                "name": "overview",
                "verify": [
                    {"exists": "{temp}/out.txt"},
                    {"contains": {"file": "{temp}/s.json", "text": "volume"}},
                ],
            }
        ],
    }
    checks = load(tmp_path, data).demos[0].verify
    assert checks[0] == VerifyCheck("exists", "{temp}/out.txt")
    assert checks[1].kind == "contains"
    assert checks[1].text == "volume"


def test_unknown_verify_check_is_rejected(tmp_path):
    data = {**BASE, "demos": [{"id": 1, "name": "overview", "verify": [{"bigger_than": 5}]}]}
    with pytest.raises(SystemExit, match="unknown verify check"):
        load(tmp_path, data)


def test_contains_needs_file_and_text(tmp_path):
    data = {**BASE, "demos": [{"id": 1, "name": "overview", "verify": [{"contains": {}}]}]}
    with pytest.raises(SystemExit, match="needs 'file' and 'text'"):
        load(tmp_path, data)
