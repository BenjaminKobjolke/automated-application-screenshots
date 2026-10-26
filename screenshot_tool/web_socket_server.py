"""Origin-restricted WebSocket transport for embedded web demo connectors.

The message shapes are documented in ``docs/WEB.md``.
"""

from __future__ import annotations

import json
import queue
import threading
from typing import Any

from websockets.exceptions import ConnectionClosed
from websockets.sync.server import Server, ServerConnection, serve

from .app_logger import AppLogger
from .demo_server import DemoEvent, parse_event_line


class WebDemoServer:
    """Accept WebSocket demo events from one configured web application origin."""

    def __init__(self, origin: str) -> None:
        self._events: queue.Queue[DemoEvent] = queue.Queue()
        self._lock = threading.Lock()
        self._connection: ServerConnection | None = None
        self._start: dict[str, Any] | None = None
        self._start_sent = False
        self._server: Server = serve(
            self._handle_connection,
            "127.0.0.1",
            0,
            origins=[origin],
        )
        self._thread = threading.Thread(target=self._server.serve_forever, daemon=True)
        self._thread.start()

    @property
    def port(self) -> int:
        """Return the ephemeral loopback port used by the server."""
        return int(self._server.socket.getsockname()[1])

    @property
    def connected(self) -> bool:
        """Whether a browser page currently holds a WebSocket connection."""
        with self._lock:
            return self._connection is not None

    def set_start(self, payload: dict[str, Any]) -> None:
        """Set the one-time start message sent on the first accepted connection."""
        with self._lock:
            self._start = payload
            connection = self._connection
            if connection is not None and not self._start_sent:
                self._send_start(connection)

    def poll(self) -> DemoEvent | None:
        """Return the next parsed event without waiting, or ``None`` if empty."""
        try:
            return self._events.get_nowait()
        except queue.Empty:
            return None

    def send(self, payload: dict[str, Any]) -> None:
        """Send one JSON message to the active page, logging navigation races."""
        with self._lock:
            connection = self._connection
            if connection is None:
                AppLogger.info("Web demo page disconnected before a command could be sent.")
                return
            try:
                connection.send(json.dumps(payload))
            except ConnectionClosed as error:
                AppLogger.info(f"Web demo page disconnected while sending a command: {error}")

    def _send_start(self, connection: ServerConnection) -> None:
        assert self._start is not None
        try:
            connection.send(json.dumps(self._start))
            self._start_sent = True
        except ConnectionClosed as error:
            AppLogger.info(f"Web demo page disconnected before start could be sent: {error}")

    def _handle_connection(self, connection: ServerConnection) -> None:
        with self._lock:
            self._connection = connection
            if self._start is not None and not self._start_sent:
                self._send_start(connection)
        try:
            while True:
                try:
                    message = connection.recv(timeout=0.1)
                except TimeoutError:
                    continue
                if not isinstance(message, str):
                    AppLogger.info("Ignoring binary web demo event; expected a text message.")
                    continue
                try:
                    self._events.put(parse_event_line(message))
                except ValueError as error:
                    AppLogger.info(f"Ignoring malformed web demo event: {error}")
        except ConnectionClosed:
            pass
        finally:
            with self._lock:
                if self._connection is connection:
                    self._connection = None

    def close(self) -> None:
        """Stop accepting clients and wait for the server thread to finish."""
        self._server.shutdown()
        self._thread.join(timeout=2)

    def __enter__(self) -> WebDemoServer:
        return self

    def __exit__(self, *_: object) -> None:
        self.close()
