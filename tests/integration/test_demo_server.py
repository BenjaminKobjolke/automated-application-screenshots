"""Integration tests for DemoServer over a real localhost socket."""

import socket
import threading
import time

from screenshot_tool.demo_server import DemoServer


def client_thread(port: int, lines: list[bytes]) -> threading.Thread:
    def run() -> None:
        with socket.create_connection(("127.0.0.1", port), timeout=5) as conn:
            for line in lines:
                conn.sendall(line)
                time.sleep(0.02)

    thread = threading.Thread(target=run, daemon=True)
    thread.start()
    return thread


def test_server_receives_typed_events():
    server = DemoServer()
    thread = client_thread(
        server.port,
        [
            b'{"event": "demo_started", "demo": 1, "hwnd": 4242}\n',
            b"this is garbage\n",
            b'{"event": "screenshot", "name": "shot-a"}\n',
            b'{"event": "demo_ended", "demo": 1}\n',
        ],
    )
    try:
        assert server.accept(timeout=5)

        started = server.next_event(timeout=5)
        assert started is not None and started.event == "demo_started" and started.demo == 1
        assert started.hwnd == 4242

        # Garbage line is logged and skipped, next real event comes through
        shot = server.next_event(timeout=5)
        assert shot is not None and shot.event == "screenshot" and shot.name == "shot-a"

        ended = server.next_event(timeout=5)
        assert ended is not None and ended.event == "demo_ended"
    finally:
        thread.join(timeout=5)
        server.close()


def test_accept_times_out_without_client():
    server = DemoServer()
    try:
        assert not server.accept(timeout=0.2)
    finally:
        server.close()


def test_next_event_times_out_on_silence():
    server = DemoServer()
    conn = socket.create_connection(("127.0.0.1", server.port), timeout=5)
    try:
        assert server.accept(timeout=5)
        assert server.next_event(timeout=0.2) is None
    finally:
        conn.close()
        server.close()
