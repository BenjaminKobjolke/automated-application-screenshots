"""Token-protected loopback control channel for detached live sessions."""

from __future__ import annotations

import hmac
import json
import math
import os
import socket
import tempfile
import threading
from dataclasses import dataclass
from pathlib import Path
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from .live_cli import LiveCLI

_SESSION_FILE = "live-session.json"
_CONNECTION_TIMEOUT = 10.0
_CONNECT_TIMEOUT = 5.0


class SessionGone(Exception):
    """The detached live session is missing or cannot answer requests."""


@dataclass(frozen=True)
class SessionFile:
    """Connection details persisted in the caller-selected session folder."""

    port: int
    token: str
    pid: int
    reply_timeout: float

    def write(self, folder: str | Path) -> None:
        """Atomically write this session's control details."""
        directory = Path(folder)
        directory.mkdir(parents=True, exist_ok=True)
        path = directory / _SESSION_FILE
        temporary: str | None = None
        try:
            with tempfile.NamedTemporaryFile(
                mode="w", encoding="utf-8", dir=directory, delete=False
            ) as stream:
                temporary = stream.name
                json.dump(
                    {
                        "port": self.port,
                        "token": self.token,
                        "pid": self.pid,
                        "reply_timeout": self.reply_timeout,
                    },
                    stream,
                    separators=(",", ":"),
                )
                stream.write("\n")
            os.replace(temporary, path)
        finally:
            if temporary is not None and os.path.exists(temporary):
                os.unlink(temporary)

    @classmethod
    def read(cls, folder: str | Path) -> SessionFile | None:
        """Read a valid session file, tolerating missing or malformed data."""
        try:
            data = json.loads((Path(folder) / _SESSION_FILE).read_text(encoding="utf-8"))
            if not isinstance(data, dict):
                return None
            port, token, pid, reply_timeout = (
                data["port"],
                data["token"],
                data["pid"],
                data["reply_timeout"],
            )
            if (
                not isinstance(port, int)
                or isinstance(port, bool)
                or not 1 <= port <= 65535
                or not isinstance(token, str)
                or not token
                or not isinstance(pid, int)
                or isinstance(pid, bool)
                or pid <= 0
                or not isinstance(reply_timeout, (int, float))
                or isinstance(reply_timeout, bool)
                or not math.isfinite(reply_timeout)
                or reply_timeout <= 0
            ):
                return None
            return cls(port, token, pid, float(reply_timeout))
        except (OSError, UnicodeError, json.JSONDecodeError, KeyError, TypeError, ValueError):
            return None

    @staticmethod
    def remove(folder: str | Path) -> None:
        """Remove the session file if it exists."""
        try:
            (Path(folder) / _SESSION_FILE).unlink()
        except FileNotFoundError:
            pass


class ControlServer:
    """Serve one authenticated JSON command per loopback connection."""

    def __init__(self) -> None:
        self._server = socket.create_server(("127.0.0.1", 0))
        self._server.settimeout(0.5)
        self._closed = threading.Event()

    @property
    def port(self) -> int:
        """Return the ephemeral loopback port this server listens on."""
        return int(self._server.getsockname()[1])

    def serve(self, cli: LiveCLI, token: str) -> None:
        """Accept authenticated requests until the CLI handles ``stop``."""
        try:
            while not self._closed.is_set():
                try:
                    connection, _ = self._server.accept()
                except TimeoutError:
                    continue
                with connection:
                    connection.settimeout(_CONNECTION_TIMEOUT)
                    try:
                        received = _receive_lines(connection, 2)
                        supplied_token = received[0].decode("utf-8").rstrip("\r")
                        line = received[1].decode("utf-8").rstrip("\r")
                        if not hmac.compare_digest(supplied_token, token):
                            response = {"ok": False, "error": "invalid session token"}
                            keep_going = True
                        else:
                            reply = cli.respond(line)
                            response = reply.response
                            keep_going = reply.keep_going
                        connection.sendall(
                            json.dumps(response, separators=(",", ":")).encode("utf-8")
                            + b"\n"
                        )
                        if not keep_going:
                            return
                    except (OSError, UnicodeError, TimeoutError):
                        continue
        finally:
            self.close()

    def close(self) -> None:
        """Stop accepting new requests."""
        if not self._closed.is_set():
            self._closed.set()
            self._server.close()


def send_line(
    folder: str | Path, line: str, timeout: float | None = None
) -> dict[str, object]:
    """Send one command to a session and return its JSON response."""
    session = SessionFile.read(folder)
    if session is None:
        raise SessionGone(f"no live session in {folder}")
    try:
        with socket.create_connection(
            ("127.0.0.1", session.port), timeout=_CONNECT_TIMEOUT
        ) as connection:
            connection.settimeout(session.reply_timeout if timeout is None else timeout)
            request = session.token.encode("utf-8") + b"\n" + line.encode("utf-8") + b"\n"
            connection.sendall(request)
            response_line = _receive_lines(connection, 1)[0]
    except (ConnectionError, OSError, TimeoutError) as error:
        if isinstance(error, (TimeoutError, socket.timeout)):
            message = f"timed out waiting for live session in {folder}"
        elif isinstance(error, (ConnectionRefusedError, ConnectionAbortedError)):
            message = f"live session in {folder} is not running"
        else:
            message = f"live session in {folder} closed before replying"
        raise SessionGone(message) from error
    try:
        response = json.loads(response_line)
    except (UnicodeError, json.JSONDecodeError) as error:
        raise SessionGone(f"live session in {folder} returned an invalid reply") from error
    if not isinstance(response, dict):
        raise SessionGone(f"live session in {folder} returned an invalid reply")
    if response.get("error") == "invalid session token":
        raise SessionGone(f"live session in {folder} rejected its session token")
    return response


def _receive_lines(connection: socket.socket, count: int) -> list[bytes]:
    """Read exactly ``count`` newline-terminated protocol lines."""
    buffer = bytearray()
    lines: list[bytes] = []
    while len(lines) < count:
        chunk = connection.recv(4096)
        if not chunk:
            raise ConnectionError("control connection closed before the reply was complete")
        buffer.extend(chunk)
        while b"\n" in buffer and len(lines) < count:
            newline = buffer.index(b"\n")
            lines.append(bytes(buffer[:newline]))
            del buffer[: newline + 1]
    return lines
