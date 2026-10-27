"""TCP server receiving demo lifecycle events from the target app.

Protocol (see docs/AUTOMATION_INTERFACE.md): the app connects and sends one
JSON object per newline-terminated UTF-8 line: ``demo_started``,
``screenshot`` (named still request), ``demo_ended``. Network mode adds the
tool -> app ``start`` command, inline PNG stills, ``error``, and ``video`` (a
JSON header followed by that many raw mp4 bytes).
"""

import json
import socket
from typing import Any

from .app_logger import AppLogger
from .demo_protocol import KNOWN_EVENTS, DemoEvent, ScreenInfo, parse_event_line

__all__ = ["KNOWN_EVENTS", "DemoEvent", "DemoServer", "ScreenInfo", "parse_event_line"]


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
        # A hot restart reconnects on a fresh socket. Discard any incomplete
        # line buffered from the old isolate before reading the new connection.
        if self._conn is not None:
            self._conn.close()
            self._conn = None
        self._buffer = b""
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
