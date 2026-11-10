"""Tests for deciding when an idle warning should interrupt a screenshot run."""

import subprocess
import sys
import tkinter

import pytest

from screenshot_tool import idle_guard
from screenshot_tool.live_config import LiveSettings, LiveTarget
from screenshot_tool.web_config import WebSettings


@pytest.mark.parametrize(
    ("title", "class_name", "expected"),
    [
        ("Screenshots finished", "TkTopLevel", True),
        ("Screenshots finished", "CabinetWClass", False),
        ("Screenshots are about to start", "TkTopLevel", False),
        ("", "", False),
    ],
)
def test_is_leftover_alert_matches_only_our_completion_window(title, class_name, expected):
    assert idle_guard._is_leftover_alert(title, class_name) is expected


def test_warn_if_active_skips_dialog_when_pc_is_idle(monkeypatch):
    shown = []
    monkeypatch.setattr(idle_guard, "seconds_since_input", lambda: idle_guard.IDLE_THRESHOLD_S)
    monkeypatch.setattr(idle_guard, "show_countdown", shown.append)

    assert idle_guard.warn_if_active() is False

    assert shown == []


def test_warn_if_active_shows_countdown_when_pc_was_recently_used(monkeypatch):
    shown = []
    monkeypatch.setattr(idle_guard, "seconds_since_input", lambda: 5.0)
    monkeypatch.setattr(idle_guard, "show_countdown", shown.append)

    assert idle_guard.warn_if_active() is True

    assert shown == [idle_guard.COUNTDOWN_S]


def test_warn_if_active_logs_and_continues_when_dialog_cannot_open(monkeypatch):
    warnings = []

    def fail_to_open(_seconds):
        raise tkinter.TclError("no interactive desktop")

    monkeypatch.setattr(idle_guard, "seconds_since_input", lambda: 0.0)
    monkeypatch.setattr(idle_guard, "show_countdown", fail_to_open)
    monkeypatch.setattr(idle_guard.AppLogger, "warning", warnings.append)

    assert idle_guard.warn_if_active() is False
    assert len(warnings) == 1
    assert "no interactive desktop" in warnings[0]


def test_notify_done_starts_detached_alert_process(monkeypatch):
    calls = []

    def record_process(*args, **kwargs):
        calls.append((args, kwargs))

    monkeypatch.setattr(idle_guard.subprocess, "Popen", record_process)

    idle_guard.notify_done()

    assert len(calls) == 1
    args, kwargs = calls[0]
    assert args[0][0] == sys.executable
    assert kwargs["creationflags"] & subprocess.DETACHED_PROCESS


def test_notify_done_logs_and_continues_when_process_cannot_start(monkeypatch):
    warnings = []

    def fail_to_start(*_args, **_kwargs):
        raise OSError("process launch failed")

    monkeypatch.setattr(idle_guard.subprocess, "Popen", fail_to_start)
    monkeypatch.setattr(idle_guard.AppLogger, "warning", warnings.append)

    assert idle_guard.notify_done() is None
    assert len(warnings) == 1
    assert "process launch failed" in warnings[0]


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
