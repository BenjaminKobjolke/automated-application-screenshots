"""Tests for target-specific timeouts on detached session startup."""

import io
from unittest.mock import MagicMock

import pytest

from screenshot_tool import live_detached
from screenshot_tool.live_config import LiveSettings, LiveTarget
from screenshot_tool.live_control import SessionFile


@pytest.mark.parametrize(
    ("target", "stages"),
    [(LiveTarget.ANDROID_EMULATOR, 4), (LiveTarget.WINDOWS, 2)],
)
def test_start_reply_timeout_accounts_for_target_start_stages(target, stages, tmp_path):
    settings = LiveSettings(target=target, port=8766, project_dir=tmp_path, start_timeout=10)

    assert live_detached.start_reply_timeout(settings) == 10 * stages + 60


def test_start_uses_target_timeout_for_start_reply(monkeypatch, tmp_path):
    settings = LiveSettings(
        target=LiveTarget.ANDROID_EMULATOR,
        port=8766,
        project_dir=tmp_path,
        start_timeout=10,
    )
    process = MagicMock()
    process.stdin = io.BytesIO()
    session_file = SessionFile(port=1234, token="token", pid=123, reply_timeout=70)
    monkeypatch.setattr(live_detached, "_spawn_server", lambda *_args: process)
    monkeypatch.setattr(live_detached, "_is_server_process", lambda _pid: False)
    monkeypatch.setattr(SessionFile, "read", lambda _folder: session_file)
    send = MagicMock(return_value={"ok": True, "device": "emulator-5554"})
    monkeypatch.setattr(live_detached, "send_line", send)

    result = live_detached.start(tmp_path / "session", settings, io.StringIO())

    assert result == 0
    send.assert_called_once_with(tmp_path / "session", '{"command":"start"}', timeout=100.0)
