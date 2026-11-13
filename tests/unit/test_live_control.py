"""Tests for the detached live-session control channel."""

from __future__ import annotations

import json
import socket
import threading
from pathlib import Path
from typing import Any

import pytest

from screenshot_tool.live_cli import LiveReply
from screenshot_tool.live_control import ControlServer, SessionFile, SessionGone, send_line


def test_session_file_round_trip_and_remove(tmp_path: Path) -> None:
    session = SessionFile(port=43210, token="session-token", pid=1234, reply_timeout=70.0)

    session.write(tmp_path)

    assert SessionFile.read(tmp_path) == session
    assert (tmp_path / "live-session.json").is_file()
    SessionFile.remove(tmp_path)
    assert not (tmp_path / "live-session.json").exists()


@pytest.mark.parametrize("contents", [None, "not json", "{}", '{"port":"bad"}'])
def test_session_file_missing_or_malformed_returns_none(
    tmp_path: Path, contents: str | None
) -> None:
    if contents is not None:
        (tmp_path / "live-session.json").write_text(contents, encoding="utf-8")

    assert SessionFile.read(tmp_path) is None


def test_send_line_without_session_raises_session_gone(tmp_path: Path) -> None:
    with pytest.raises(SessionGone, match="no live session"):
        send_line(tmp_path, '{"command":"stop"}')


def test_send_line_to_closed_port_raises_session_gone(tmp_path: Path) -> None:
    with socket.socket() as listener:
        listener.bind(("127.0.0.1", 0))
        port = int(listener.getsockname()[1])
    SessionFile(port, "secret", 1234, 0.1).write(tmp_path)

    with pytest.raises(SessionGone, match="not running"):
        send_line(tmp_path, '{"command":"stop"}')


class _FakeCLI:
    def __init__(self) -> None:
        self.lines: list[str] = []

    def respond(self, line: str) -> LiveReply:
        self.lines.append(line)
        keep_going = json.loads(line).get("command") != "stop"
        return LiveReply({"ok": True, "received": line}, keep_going)


def _request(port: int, token: str, line: str) -> dict[str, Any]:
    with socket.create_connection(("127.0.0.1", port), timeout=2) as connection:
        connection.sendall(f"{token}\n{line}\n".encode())
        response = bytearray()
        while b"\n" not in response:
            chunk = connection.recv(4096)
            if not chunk:
                break
            response.extend(chunk)
    return json.loads(response.split(b"\n", 1)[0])


def test_control_server_checks_token_and_ends_after_stop() -> None:
    server = ControlServer()
    cli = _FakeCLI()
    thread = threading.Thread(target=server.serve, args=(cli, "right-token"), daemon=True)
    thread.start()
    try:
        invalid = _request(server.port, "wrong-token", '{"command":"anything"}')
        assert invalid == {"ok": False, "error": "invalid session token"}
        assert cli.lines == []

        valid = _request(server.port, "right-token", '{"command":"screens"}')
        assert valid["ok"] is True
        assert cli.lines == ['{"command":"screens"}']

        stopped = _request(server.port, "right-token", '{"command":"stop"}')
        assert stopped["ok"] is True
        thread.join(timeout=2)
        assert not thread.is_alive()
        assert cli.lines[-1] == '{"command":"stop"}'
    finally:
        server.close()
        thread.join(timeout=2)
