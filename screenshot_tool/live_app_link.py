"""Request and receive events on the app-side automation connection."""

import time

from .app_logger import AppLogger
from .demo_protocol import DemoEvent
from .demo_server import DemoServer
from .flutter_daemon import FlutterDaemon
from .live_config import LiveSettings
from .live_types import LiveConnectionLost, LiveError

_POLL_SECONDS = 0.1


class LiveAppLink:
    """Coordinate app commands and events with the owning Flutter daemon."""

    def __init__(self, server: DemoServer, daemon: FlutterDaemon) -> None:
        self.server = server
        self.daemon = daemon

    def accept_and_reset(self, settings: LiveSettings, timeout: float) -> None:
        """Accept the app connection and apply its configured settings."""
        deadline = time.monotonic() + timeout
        last_error: LiveConnectionLost | None = None
        while True:
            remaining = deadline - time.monotonic()
            if remaining <= 0 or not self.server.accept(remaining):
                if last_error is None:
                    raise LiveError("Flutter app did not connect before timeout", self.daemon.output)
                raise LiveError(
                    "app connection lost before 'reset_done', "
                    f"no new connection before timeout: {last_error}",
                    self.daemon.output,
                ) from last_error
            remaining = deadline - time.monotonic()
            if remaining <= 0:
                raise LiveError("Flutter app did not connect before timeout", self.daemon.output)
            try:
                self.server.send({"command": "reset", "settings": settings.app_settings})
                self.await_event("reset_done", remaining)
                return
            except OSError as error:
                last_error = LiveConnectionLost(
                    f"app connection lost while sending 'reset': {error}", self.daemon.output
                )
            except LiveConnectionLost as error:
                last_error = error
            AppLogger.info(f"Ignoring stale app connection: {last_error}")

    def request(
        self, request: dict[str, object], expected: str, timeout: float
    ) -> DemoEvent:
        """Send one app command and wait for its matching event."""
        self.server.send(request)
        return self.await_event(expected, timeout)

    def await_event(self, expected: str, timeout: float) -> DemoEvent:
        """Wait for an event while detecting daemon exit and app errors."""
        deadline = time.monotonic() + timeout
        while time.monotonic() < deadline:
            if not self.daemon.is_running():
                raise LiveError("Flutter process exited while waiting for the app", self.daemon.output)
            try:
                event = self.server.next_event(min(_POLL_SECONDS, deadline - time.monotonic()))
            except (ConnectionError, OSError) as error:
                raise LiveConnectionLost(
                    f"app connection lost while waiting for {expected!r}: {error}",
                    self.daemon.output,
                ) from error
            if event is None:
                continue
            if event.event == "error":
                raise LiveError(event.message or "app command failed")
            if event.event == expected:
                return event
        raise LiveError(f"timed out waiting for app event {expected!r}", self.daemon.output)
