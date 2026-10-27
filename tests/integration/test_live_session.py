"""Integration coverage for the live session using a local fake daemon/app."""

from __future__ import annotations

from pathlib import Path

import pytest

from screenshot_tool.android_emulator import AndroidEmulator
from screenshot_tool.demo_server import ScreenInfo
from screenshot_tool.live_config import LiveSettings, LiveTarget
from screenshot_tool.live_session import (
    LiveError,
    LiveSession,
    ShotRequest,
    ShotTheme,
)


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


def test_language_reaches_navigate_and_does_not_stick(live_session: LiveSession, tmp_path: Path):
    live_session.start()

    localized = tmp_path / "localized.png"
    live_session.shot(ShotRequest("home", localized, language="de"))
    assert b"language=de" in localized.read_bytes()

    plain = tmp_path / "plain.png"
    live_session.shot(ShotRequest("home", plain))
    assert plain.read_bytes() == b"fake-png"


def test_record_id_on_plain_screen_returns_app_error(live_session: LiveSession, tmp_path: Path):
    live_session.start()

    with pytest.raises(LiveError, match="takes no record id"):
        live_session.shot(ShotRequest("home", tmp_path / "home.png", record_id=1))


def test_unknown_section_returns_app_error(live_session: LiveSession, tmp_path: Path):
    live_session.start()

    with pytest.raises(LiveError, match="unknown section nope for habit_edit"):
        live_session.shot(ShotRequest("habit_edit", tmp_path / "unknown.png", section="nope"))


def test_android_start_without_sdk_names_missing_program(tmp_path: Path, free_port: int):
    settings = LiveSettings(
        target=LiveTarget.ANDROID_EMULATOR,
        avd="Test_AVD",
        port=free_port,
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
