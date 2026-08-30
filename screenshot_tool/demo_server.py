"""TCP server receiving demo lifecycle events from the target app.

Protocol (see docs/AUTOMATION_INTERFACE.md): the app connects and sends one
JSON object per newline-terminated UTF-8 line: ``demo_started``,
``screenshot`` (named still request), ``demo_ended``. Network mode adds the
tool -> app ``start`` command, inline PNG stills, ``error``, and ``video`` (a
JSON header followed by that many raw mp4 bytes).
"""

import base64
import json
import socket
from dataclasses import dataclass
from typing import Any

from .app_logger import AppLogger

KNOWN_EVENTS = ("demo_started", "screenshot", "demo_ended", "video", "error")


@dataclass(frozen=True)
class DemoEvent:
    """One typed event received from the target application."""

    event: str
    demo: int | None
    name: str | None
    hwnd: int | None
    # Network mode: the still itself (the phone has no window to capture)
    png: bytes | None = None
    # Network mode: byte count of the mp4 that follows a ``video`` header
    size: int | None = None
    message: str | None = None


def parse_event_line(line: str) -> DemoEvent:
    """Parse one protocol line into a DemoEvent.

    Raises:
        ValueError: If the line is not JSON or lacks a known 'event' key.
    """
    try:
        data = json.loads(line)
    except json.JSONDecodeError as e:
        raise ValueError(f"not JSON: {line!r}") from e
    if not isinstance(data, dict) or data.get("event") not in KNOWN_EVENTS:
        raise ValueError(f"unknown demo event: {line!r}")
    return DemoEvent(
        event=data["event"],
        demo=data.get("demo"),
        name=data.get("name"),
        hwnd=data.get("hwnd"),
        png=base64.b64decode(data["png"]) if isinstance(data.get("png"), str) else None,
        size=data.get("size"),
        message=data.get("message"),
    )


class DemoServer:
    """Accepts one app connection and yields its events with timeouts."""

    def __init__(self, host: str = "127.0.0.1", port: int = 0) -> None:
        self._server = socket.create_server((host, port))
        self._conn: socket.socket | None = None
        self._buffer = b""

    @property
    def port(self) -> int:
        return int(self._server.getsockname()[1])

    def accept(self, timeout: float) -> bool:
        """Wait for the app to connect.

        Returns:
            True once connected, False on timeout.
        """
        self._server.settimeout(timeout)
        try:
            self._conn, _ = self._server.accept()
        except TimeoutError:
            return False
        return True

    def next_event(self, timeout: float) -> DemoEvent | None:
        """Read the next event line.

        Returns:
            The event, or None on timeout.

        Raises:
            ConnectionError: If the app disconnected.
        """
        assert self._conn is not None, "next_event() before accept()"
        self._conn.settimeout(timeout)
        while True:
            newline = self._buffer.find(b"\n")
            if newline != -1:
                line = self._buffer[:newline].decode("utf-8", errors="replace").strip()
                self._buffer = self._buffer[newline + 1 :]
                if not line:
                    continue
                try:
                    return parse_event_line(line)
                except ValueError as e:
                    AppLogger.info(f"Ignoring malformed demo event: {e}")
                    continue
            try:
                chunk = self._conn.recv(4096)
            except TimeoutError:
                return None
            if not chunk:
                raise ConnectionError("demo app closed the event connection")
            self._buffer += chunk

    def send(self, payload: dict[str, Any]) -> None:
        """Send one JSON line to the app (network mode commands)."""
        assert self._conn is not None, "send() before accept()"
        self._conn.sendall(json.dumps(payload).encode("utf-8") + b"\n")

    def read_exact(self, size: int, timeout: float) -> bytes:
        """Read ``size`` raw bytes that follow a ``video`` header.

        Raises:
            ConnectionError: If the app disconnected mid-transfer.
            TimeoutError: If no bytes arrive for ``timeout`` seconds.
        """
        assert self._conn is not None, "read_exact() before accept()"
        self._conn.settimeout(timeout)
        # Line reads may already have pulled the start of the blob in
        data, self._buffer = self._buffer[:size], self._buffer[size:]
        while len(data) < size:
            chunk = self._conn.recv(min(65536, size - len(data)))
            if not chunk:
                raise ConnectionError("demo app closed the connection mid-video")
            data += chunk
        return data

    def close(self) -> None:
        if self._conn is not None:
            self._conn.close()
            self._conn = None
        self._server.close()
