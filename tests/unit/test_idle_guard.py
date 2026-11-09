"""Tests for deciding when an idle warning should interrupt a screenshot run."""

import tkinter

import pytest

from screenshot_tool import idle_guard
from screenshot_tool.live_config import LiveSettings, LiveTarget
from screenshot_tool.web_config import WebSettings


def test_warn_if_active_skips_dialog_when_pc_is_idle(monkeypatch):
    shown = []
    monkeypatch.setattr(idle_guard, "seconds_since_input", lambda: idle_guard.IDLE_THRESHOLD_S)
    monkeypatch.setattr(idle_guard, "show_countdown", shown.append)

    idle_guard.warn_if_active()

    assert shown == []


def test_warn_if_active_shows_countdown_when_pc_was_recently_used(monkeypatch):
    shown = []
    monkeypatch.setattr(idle_guard, "seconds_since_input", lambda: 5.0)
    monkeypatch.setattr(idle_guard, "show_countdown", shown.append)

    idle_guard.warn_if_active()

    assert shown == [idle_guard.COUNTDOWN_S]


def test_warn_if_active_logs_and_continues_when_dialog_cannot_open(monkeypatch):
    warnings = []

    def fail_to_open(_seconds):
        raise tkinter.TclError("no interactive desktop")

    monkeypatch.setattr(idle_guard, "seconds_since_input", lambda: 0.0)
    monkeypatch.setattr(idle_guard, "show_countdown", fail_to_open)
    monkeypatch.setattr(idle_guard.AppLogger, "warning", warnings.append)

    assert idle_guard.warn_if_active() is None
    assert len(warnings) == 1
    assert "no interactive desktop" in warnings[0]


def _live_settings(target=LiveTarget.WINDOWS, headless=False):
    return LiveSettings(target=target, port=1234, headless=headless)


@pytest.mark.parametrize(
    ("kwargs", "expected"),
    [
        ({"list_mode": True}, False),
        ({"compose": True}, False),
        ({"web_settings": WebSettings(base_url="https://example.test")}, False),
        (
            {
                "live": True,
                "live_settings": _live_settings(LiveTarget.ANDROID_EMULATOR, headless=True),
            },
            False,
        ),
        ({}, True),
        ({"demo": True}, True),
        (
            {
                "demo": True,
                "web_settings": WebSettings(
                    base_url="https://example.test", headless=True
                ),
            },
            True,
        ),
        ({"web_settings": WebSettings(base_url="https://example.test", headless=False)}, True),
        ({"live": True, "live_settings": _live_settings()}, True),
    ],
)
def test_shows_windows_for_capture_modes(kwargs, expected):
    arguments = {
        "list_mode": False,
        "demo": False,
        "compose": False,
        "live": False,
        "live_settings": None,
        "web_settings": None,
    }
    arguments.update(kwargs)

    assert idle_guard.shows_windows(**arguments) is expected
