"""Small Flutter machine-protocol stand-in for live-session integration tests.

Like ``flutter run --machine``, it drops stdin lines not wrapped in ``[ ]``.
"""

from __future__ import annotations

import base64
import json
import os
import socket
import sys
import threading
import time
from pathlib import Path

PNG = base64.b64encode(b"fake-png").decode("ascii")
OUTPUT_LOCK = threading.Lock()


def emit(message: dict[str, object]) -> None:
    with OUTPUT_LOCK:
        sys.stdout.write(json.dumps([message]) + "\n")
        sys.stdout.flush()


def app_reader(connection: socket.socket) -> None:
    with connection, connection.makefile("r", encoding="utf-8") as stream:
        for line in stream:
            command = json.loads(line)
            name = command.get("command")
            if name == "reset":
                event: dict[str, object] = {"event": "reset_done"}
            elif name == "list_screens":
                event = {"event": "screens", "screens": [{"name": "home"}]}
            elif name == "navigate":
                event = {"event": "navigated", "screen": command["screen"]}
            elif name == "screenshot":
                event = {"event": "screenshot", "name": command["name"], "png": PNG}
            else:
                event = {"event": "error", "message": f"unknown command: {name}"}
            connection.sendall(json.dumps(event).encode() + b"\n")


def connect_app(host: str, port: int) -> None:
    deadline = time.monotonic() + 15
    while time.monotonic() < deadline:
        try:
            connection = socket.create_connection((host, port), timeout=1)
            threading.Thread(target=app_reader, args=(connection,), daemon=True).start()
            return
        except OSError:
            time.sleep(0.05)
    raise RuntimeError("fake app could not connect to the automation server")


def run() -> None:
    prefix = "--dart-define=AUTOMATION_HOST="
    host_arg = next(item[len(prefix) :] for item in sys.argv if item.startswith(prefix))
    host, port_text = host_arg.rsplit(":", 1)
    port = int(port_text)
    control = Path(os.environ["FLUTTER_FAKE_CONTROL"])
    emit({"event": "app.started", "params": {"appId": "fake-app"}})
    connect_app(host, port)
    for line in sys.stdin:
        stripped = line.strip()
        if not stripped.startswith("[") or not stripped.endswith("]"):
            continue
        for request in json.loads(stripped):
            method = request.get("method")
            params = request.get("params", {})
            if method == "app.restart":
                full = params.get("fullRestart") is True
                mode = control.read_text().strip() if control.exists() else ""
                if mode == "exit":
                    emit({"id": request["id"], "result": {"code": 1, "message": "process exited"}})
                    return
                if mode == "compile" or (mode == "refuse_reload" and not full):
                    result = {"code": 1, "message": "fake compile error at sample.dart:7"}
                else:
                    result = {"code": 0}
                    if full:
                        connect_app(host, port)
                emit({"id": request["id"], "result": result})
            elif method == "app.stop":
                emit({"id": request["id"], "result": {"code": 0}})
                return


if __name__ == "__main__":
    run()
