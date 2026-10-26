import time

import pytest
from websockets.exceptions import InvalidStatus
from websockets.sync.client import connect

from screenshot_tool.demo_server import DemoEvent
from screenshot_tool.web_socket_server import WebDemoServer


def test_server_restricts_origin_sends_start_and_accepts_reconnects() -> None:
    with WebDemoServer("https://example.test") as server:
        server.set_start({"command": "start", "demo": 1})
        with connect(
            f"ws://127.0.0.1:{server.port}/", origin="https://example.test"
        ) as client:
            assert client.recv(timeout=2) == '{"command": "start", "demo": 1}'
            client.send('{"event":"demo_started","demo":1}')
            deadline = time.monotonic() + 2
            event = None
            while event is None and time.monotonic() < deadline:
                event = server.poll()
                time.sleep(0.01)
            assert event == DemoEvent("demo_started", 1, None, None)
            server.send({"command": "screenshot_done", "name": "overview"})
            assert client.recv(timeout=2) == '{"command": "screenshot_done", "name": "overview"}'

        with connect(
            f"ws://127.0.0.1:{server.port}/", origin="https://example.test"
        ) as client:
            with pytest.raises(TimeoutError):
                client.recv(timeout=0.2)
            client.send('{"event":"demo_ended","demo":1}')
            deadline = time.monotonic() + 2
            event = None
            while event is None and time.monotonic() < deadline:
                event = server.poll()
                time.sleep(0.01)
            assert event is not None and event.event == "demo_ended"

        with pytest.raises(InvalidStatus):
            connect(f"ws://127.0.0.1:{server.port}/", origin="https://evil.test", open_timeout=2)
