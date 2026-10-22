"""Integration coverage for the live session using a local fake daemon/app."""

from __future__ import annotations

import json
import os
import socket
import sys
from pathlib import Path

import pytest

from screenshot_tool.android_emulator import AndroidEmulator
from screenshot_tool.live_config import LiveSettings, LiveTarget
from screenshot_tool.live_session import LiveError, LiveSession, ReloadOutcome, ShotRequest, ShotTheme
from screenshot_tool.demo_server import ScreenInfo

FAKE_DAEMON = Path(__file__).parents[1] / "fixtures" / "fake_flutter_daemon.py"


def available_port() -> int:
    with socket.socket() as server:
        server.bind(("127.0.0.1", 0))
        return int(server.getsockname()[1])


@pytest.fixture
def live_session(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> LiveSession:
    port = available_port()
    control = tmp_path / "control"
    monkeypatch.setenv("FLUTTER_FAKE_CONTROL", str(control))
    settings = LiveSettings(
        target=LiveTarget.WINDOWS,
        port=port,
        flutter=(sys.executable, str(FAKE_DAEMON)),
        project_dir=tmp_path,
        start_timeout=10,
    )
    session = LiveSession(settings)
    yield session
    session.stop()


def test_start_screens_and_png_capture(live_session: LiveSession, tmp_path: Path):
    live_session.start()

    assert live_session.screens() == (
        ScreenInfo(name="home"),
        ScreenInfo(name="habit_edit", sections=("additional_information",)),
        ScreenInfo(name="todo_detail", record_id="todo id"),
    )
    image = tmp_path / "nested" / "home.png"
    live_session.shot(ShotRequest("home", image))
    assert image.read_bytes() == b"fake-png"


def test_shot_options_reach_app_and_save_png(live_session: LiveSession, tmp_path: Path):
    live_session.start()

    dark = tmp_path / "dark.png"
    live_session.shot(ShotRequest("habit_edit", dark, ShotTheme.DARK, "additional_information"))
    assert b"theme=dark" in dark.read_bytes()
    assert b"section=additional_information" in dark.read_bytes()

    light = tmp_path / "light.png"
    live_session.shot(ShotRequest("home", light, ShotTheme.LIGHT))
    assert b"theme=light" in light.read_bytes()

    full = tmp_path / "full.png"
    live_session.shot(ShotRequest("home", full, full=True))
    assert b"full=True" in full.read_bytes()


def test_record_id_reaches_navigate(live_session: LiveSession, tmp_path: Path):
    live_session.start()

    image = tmp_path / "todo.png"
    live_session.shot(ShotRequest("todo_detail", image, record_id=11551))

    assert b"record_id=11551" in image.read_bytes()


def test_record_id_on_plain_screen_returns_app_error(live_session: LiveSession, tmp_path: Path):
    live_session.start()

    with pytest.raises(LiveError, match="takes no record id"):
        live_session.shot(ShotRequest("home", tmp_path / "home.png", record_id=1))


def test_unknown_section_returns_app_error(live_session: LiveSession, tmp_path: Path):
    live_session.start()

    with pytest.raises(LiveError, match="unknown section nope for habit_edit"):
        live_session.shot(ShotRequest("habit_edit", tmp_path / "unknown.png", section="nope"))


def test_reload_succeeds_without_reconnecting(live_session: LiveSession):
    live_session.start()

    assert live_session.reload().outcome is ReloadOutcome.RELOADED


def test_daemon_ignores_unwrapped_requests(live_session: LiveSession, monkeypatch: pytest.MonkeyPatch):
    live_session.start()
    monkeypatch.setattr(
        "screenshot_tool.flutter_daemon.encode_request",
        lambda request: json.dumps(request) + "\n",
    )

    result = live_session.daemon.restart(full=False, timeout=1)

    assert not result.success
    assert result.message == "Flutter restart timed out"
    assert result.timed_out


def test_restart_timeout_reports_unresponsive_and_stops_app(
    live_session: LiveSession, monkeypatch: pytest.MonkeyPatch
):
    live_session.start()
    Path(os.environ["FLUTTER_FAKE_CONTROL"]).write_text("hang")
    monkeypatch.setattr("screenshot_tool.live_session._COMMAND_TIMEOUT", 0.5)

    result = live_session.reload()

    assert result.outcome is ReloadOutcome.UNRESPONSIVE
    assert "stopped responding" in result.message
    assert not live_session.daemon.is_running()
    assert live_session.reload().outcome is ReloadOutcome.RELAUNCHED
    assert live_session.daemon.is_running()


def test_hot_restart_fallback_reconnects_and_resets(live_session: LiveSession):
    live_session.start()
    control = Path(os.environ["FLUTTER_FAKE_CONTROL"])
    control.write_text("refuse_reload")

    result = live_session.reload()

    assert result.outcome is ReloadOutcome.RESTARTED


def test_compile_error_includes_daemon_message(live_session: LiveSession):
    live_session.start()
    control = Path(os.environ["FLUTTER_FAKE_CONTROL"])
    control.write_text("compile")

    result = live_session.reload()

    assert result.outcome is ReloadOutcome.COMPILE_ERROR
    assert "sample.dart:7" in result.message


def test_relaunches_after_daemon_exits(live_session: LiveSession):
    live_session.start()
    control = Path(os.environ["FLUTTER_FAKE_CONTROL"])
    control.write_text("exit")

    assert live_session.reload().outcome is ReloadOutcome.RELAUNCHED


def test_stop_cleans_up_daemon_process(live_session: LiveSession):
    live_session.start()
    daemon = live_session.daemon
    assert daemon.is_running()

    live_session.stop()

    assert not daemon.is_running()


def test_android_start_without_sdk_names_missing_program(tmp_path: Path):
    settings = LiveSettings(
        target=LiveTarget.ANDROID_EMULATOR,
        avd="Test_AVD",
        port=available_port(),
        project_dir=tmp_path,
    )
    session = LiveSession(
        settings,
        emulator=AndroidEmulator(environ={"PATH": str(tmp_path / "empty-path")}),
    )

    with pytest.raises(LiveError) as error:
        session.start()

    assert "'adb'" in error.value.message
    assert "ANDROID_HOME" in error.value.message
    assert "ANDROID_SDK_ROOT" in error.value.message
