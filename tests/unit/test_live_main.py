"""Focused tests for the public live CLI modes."""

import json

import pytest

from screenshot_tool import main


def run_main(monkeypatch, *arguments: str) -> int:
    monkeypatch.setattr(main, "setup_utf8_console", lambda: None)
    monkeypatch.setattr("sys.argv", ["screenshot-tool", *arguments])
    return main.main()


def test_live_start_requires_config(monkeypatch):
    with pytest.raises(SystemExit) as error:
        run_main(monkeypatch, "--live-start", "session")

    assert error.value.code == 2


def test_live_start_cannot_be_combined_with_live(monkeypatch):
    with pytest.raises(SystemExit) as error:
        run_main(monkeypatch, "--config", "config.json", "--live", "--live-start", "session")

    assert error.value.code == 2


def test_live_send_requires_folder_and_json(monkeypatch):
    with pytest.raises(SystemExit) as error:
        run_main(monkeypatch, "--live-send", "session")

    assert error.value.code == 2


@pytest.mark.parametrize("mode", ["send", "stop"])
def test_one_shot_modes_bypass_config_and_idle_checks(monkeypatch, tmp_path, mode, capsys):
    def fail(*_args, **_kwargs):
        raise AssertionError("one-shot commands must not load config or check idle state")

    monkeypatch.setattr("screenshot_tool.main.config.load_config", fail)
    monkeypatch.setattr("screenshot_tool.main.idle_guard.warn_if_active", fail)
    if mode == "send":
        result = run_main(monkeypatch, "--live-send", str(tmp_path), '{"command":"start"}')
        assert result == 3
        assert json.loads(capsys.readouterr().out)["ok"] is False
    else:
        result = run_main(monkeypatch, "--live-stop", str(tmp_path))
        assert result == 0
        assert json.loads(capsys.readouterr().out) == {"ok": True, "stopped": False}


def test_live_start_rejects_target_options_without_live_mode(monkeypatch):
    with pytest.raises(SystemExit) as error:
        run_main(monkeypatch, "--target", "windows")

    assert error.value.code == 2
