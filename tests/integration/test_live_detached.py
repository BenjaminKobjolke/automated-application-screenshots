"""End-to-end checks for detached live-session CLI calls."""

from __future__ import annotations

import io
import json
import socket
import sys
import time
from collections.abc import Callable
from pathlib import Path

import psutil
import pytest

from screenshot_tool.live_config import LiveSettings, LiveTarget
from screenshot_tool.live_control import SessionFile, SessionGone
from screenshot_tool.live_detached import send, start, stop

FAKE_DAEMON = Path(__file__).parents[1] / "fixtures" / "fake_flutter_daemon.py"


def _available_port() -> int:
    with socket.socket() as listener:
        listener.bind(("127.0.0.1", 0))
        return int(listener.getsockname()[1])


def _settings(
    directory: Path,
    control: Path,
    monkeypatch: pytest.MonkeyPatch,
    *,
    flutter: list[str] | None = None,
) -> LiveSettings:
    monkeypatch.setenv("FLUTTER_FAKE_CONTROL", str(control))
    command = flutter or [sys.executable, str(FAKE_DAEMON)]
    return LiveSettings(
        target=LiveTarget.WINDOWS,
        port=_available_port(),
        flutter=tuple(command),
        project_dir=directory,
        start_timeout=10,
    )


def _call(action: Callable[..., int], *arguments: object) -> tuple[int, dict[str, object]]:
    output = io.StringIO()
    code = action(*arguments, output=output)
    return code, json.loads(output.getvalue())


def _wait_for_process_exit(pid: int) -> bool:
    deadline = time.monotonic() + 10
    while time.monotonic() < deadline:
        if not psutil.pid_exists(pid):
            return True
        time.sleep(0.1)
    return not psutil.pid_exists(pid)


def test_detached_session_start_send_and_stop(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    session_dir = tmp_path / "session"
    control = tmp_path / "fake-control"
    settings = _settings(tmp_path, control, monkeypatch)

    start_code, start_response = _call(start, session_dir, settings)
    assert start_code == 0
    assert start_response["ok"] is True
    assert start_response["device"] == "windows"
    session_file = session_dir / "live-session.json"
    assert session_file.exists()
    session_details = SessionFile.read(session_dir)
    assert session_details is not None
    pid = session_details.pid

    try:
        read_code, read_response = _call(send, session_dir, '{"command":"screens"}')
        assert read_code == 0
        assert read_response["screens"]

        image_path = tmp_path / "shot.png"
        shot_code, _ = _call(
            send, session_dir, json.dumps({"command": "shot", "out": str(image_path)})
        )
        assert shot_code == 0
        assert image_path.read_bytes() == b"fake-png"

        missing_code, missing_response = _call(
            send, session_dir, '{"command":"tap_text","text":"missing"}'
        )
        assert missing_code == 1
        assert missing_response["ok"] is False

        malformed_code, malformed_response = _call(send, session_dir, "{")
        assert malformed_code == 1
        assert malformed_response["ok"] is False

        duplicate_code, duplicate_response = _call(start, session_dir, settings)
        assert duplicate_code == 1
        assert duplicate_response["ok"] is False
    finally:
        stopped_code, stopped_response = _call(stop, session_dir)

    assert stopped_code == 0
    assert stopped_response["stopped"] is True
    assert _wait_for_process_exit(pid)
    assert not session_file.exists()

    missing_code, missing_response = _call(send, session_dir, '{"command":"screens"}')
    assert missing_code == 3
    assert missing_response["ok"] is False

    stopped_again_code, stopped_again_response = _call(stop, session_dir)
    assert stopped_again_code == 0
    assert stopped_again_response["stopped"] is False


def test_detached_session_failed_start_leaves_no_process_or_file(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    session_dir = tmp_path / "session"
    settings = _settings(
        tmp_path,
        tmp_path / "fake-control",
        monkeypatch,
        flutter=[sys.executable, "-c", "import sys; sys.exit(1)"],
    )

    code, response = _call(start, session_dir, settings)

    assert code == 1
    assert response["ok"] is False
    assert not (session_dir / "live-session.json").exists()
    assert not any(
        process.info["cmdline"]
        and "fake_flutter_daemon.py" in " ".join(process.info["cmdline"])
        for process in psutil.process_iter(["cmdline"])
    )


def test_stop_reports_stopped_after_fallback_cleanup(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    session_dir = tmp_path / "session"
    session_dir.mkdir()
    session = SessionFile(port=12345, token="token", pid=12345, reply_timeout=30)
    session.write(session_dir)
    cleanup_calls: list[tuple[Path, SessionFile]] = []

    def fail_control(*_args: object, **_kwargs: object) -> dict[str, object]:
        raise SessionGone("control unavailable")

    monkeypatch.setattr("screenshot_tool.live_detached.send_line", fail_control)
    monkeypatch.setattr(
        "screenshot_tool.live_detached._stop_or_kill",
        lambda folder, recorded: cleanup_calls.append((Path(folder), recorded)),
    )

    code, response = _call(stop, session_dir)

    assert code == 0
    assert response == {"ok": True, "stopped": True}
    assert cleanup_calls == [(session_dir, session)]
    assert SessionFile.read(session_dir) is None
