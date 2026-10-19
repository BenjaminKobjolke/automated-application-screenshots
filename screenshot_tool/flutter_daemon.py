"""Start and control a Flutter application through Flutter's machine daemon."""

from __future__ import annotations

import json
import queue
import shutil
import subprocess
import threading
import time
from collections import deque
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import psutil

from .live_config import LiveSettings, automation_host

_LOG_LIMIT = 100
_STOP_TIMEOUT = 3.0


def encode_request(request: dict[str, Any]) -> str:
    # Flutter silently drops stdin lines unless each request is wrapped in an array.
    return json.dumps([request]) + "\n"


@dataclass(frozen=True)
class DaemonMessage:
    """One structured event or response from Flutter's daemon."""

    event: str | None
    params: dict[str, Any]
    response_id: str | None = None
    result: Any = None
    error: Any = None


@dataclass(frozen=True)
class DaemonResult:
    """Outcome of one daemon RPC request."""

    success: bool
    message: str = ""


def parse_daemon_line(line: str) -> tuple[tuple[DaemonMessage, ...], str | None]:
    """Decode a daemon line, returning ordinary console output as log text."""
    try:
        value = json.loads(line)
    except json.JSONDecodeError:
        return (), line.rstrip("\r\n")
    if not isinstance(value, list):
        return (), line.rstrip("\r\n")

    messages: list[DaemonMessage] = []
    for item in value:
        if not isinstance(item, dict):
            continue
        params = item.get("params")
        messages.append(
            DaemonMessage(
                event=item.get("event") if isinstance(item.get("event"), str) else None,
                params=params if isinstance(params, dict) else {},
                response_id=str(item["id"]) if "id" in item else None,
                result=item.get("result"),
                error=item.get("error"),
            )
        )
    return tuple(messages), None


class FlutterDaemon:
    """Own a Flutter run process and its machine-protocol reader thread."""

    def __init__(self, settings: LiveSettings) -> None:
        self.settings = settings
        self._process: subprocess.Popen[str] | None = None
        self._messages: queue.Queue[DaemonMessage] = queue.Queue()
        self._logs: deque[str] = deque(maxlen=_LOG_LIMIT)
        self._reader: threading.Thread | None = None
        self._app_id: str | None = None
        self._request_id = 0
        self._request_lock = threading.Lock()
        self._started = threading.Event()

    def build_command(self, device: str) -> list[str]:
        """Build Flutter's machine-mode command with config-provided arguments."""
        prefix = list(self.settings.flutter)
        resolved = shutil.which(prefix[0])
        if resolved:
            prefix[0] = resolved
        return [
            *prefix,
            "run",
            "--machine",
            "-d",
            device,
            f"--dart-define=AUTOMATION_HOST={automation_host(self.settings.target, self.settings.port)}",
            *self.settings.run_args,
        ]

    @property
    def output(self) -> str:
        """Return the recent daemon and build output for error responses."""
        return "\n".join(self._logs)

    def start(self, device: str) -> None:
        """Launch Flutter and begin reading its machine protocol."""
        if self.is_running():
            raise RuntimeError("Flutter daemon is already running")
        self._messages = queue.Queue()
        self._logs.clear()
        self._app_id = None
        self._started.clear()
        self._process = subprocess.Popen(
            self.build_command(device),
            cwd=self.settings.project_dir,
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
            encoding="utf-8",
            errors="replace",
            bufsize=1,
        )
        self._reader = threading.Thread(target=self._read_output, name="flutter-daemon-reader", daemon=True)
        self._reader.start()

    def wait_for_started(self, timeout: float) -> bool:
        """Wait until Flutter reports that the application has started."""
        deadline = time.monotonic() + timeout
        while time.monotonic() < deadline and self.is_running():
            message = self._next_message(deadline)
            if message is None:
                continue
            if message.event == "app.started":
                app_id = message.params.get("appId")
                if isinstance(app_id, str):
                    self._app_id = app_id
                    self._started.set()
                    return True
            if message.error:
                self._logs.append(str(message.error))
        return False

    def restart(self, full: bool, timeout: float) -> DaemonResult:
        """Ask Flutter to hot reload or hot restart the running application."""
        if not self.is_running() or self._app_id is None:
            return DaemonResult(False, "Flutter app is not running")
        response = self._rpc(
            "app.restart",
            {"appId": self._app_id, "fullRestart": full},
            timeout,
        )
        if response is None:
            return DaemonResult(False, "Flutter restart timed out")
        if response.error:
            return DaemonResult(False, str(response.error))
        result = response.result
        code = result.get("code") if isinstance(result, dict) else None
        if not isinstance(code, int) or isinstance(code, bool) or code != 0:
            message = result.get("message") if isinstance(result, dict) else None
            return DaemonResult(False, str(message or result))
        return DaemonResult(True, "Flutter restart completed")

    def is_running(self) -> bool:
        """Whether the Flutter process is currently alive."""
        return self._process is not None and self._process.poll() is None

    def stop(self) -> None:
        """Request a graceful app stop and always terminate its process tree."""
        process = self._process
        if process is None:
            return
        if process.poll() is None and self._app_id is not None:
            self._rpc("app.stop", {"appId": self._app_id}, _STOP_TIMEOUT)
        if process.poll() is None:
            try:
                process.wait(timeout=_STOP_TIMEOUT)
            except subprocess.TimeoutExpired:
                self._kill_process_tree(process.pid)
        self._kill_process_tree(process.pid)
        self._process = None

    def _rpc(self, method: str, params: dict[str, Any], timeout: float) -> DaemonMessage | None:
        process = self._process
        if process is None or process.stdin is None:
            return None
        with self._request_lock:
            self._request_id += 1
            request_id = str(self._request_id)
            request = {"id": request_id, "method": method, "params": params}
            try:
                process.stdin.write(encode_request(request))
                process.stdin.flush()
            except (BrokenPipeError, OSError):
                return None
            deadline = time.monotonic() + timeout
            while time.monotonic() < deadline:
                message = self._next_message(deadline)
                if message is None:
                    continue
                if message.response_id == request_id:
                    return message
                if message.event:
                    self._handle_event(message)
            return None

    def _read_output(self) -> None:
        process = self._process
        if process is None or process.stdout is None:
            return
        for line in process.stdout:
            messages, log = parse_daemon_line(line)
            if log:
                self._logs.append(log)
            for message in messages:
                self._messages.put(message)

    def _next_message(self, deadline: float) -> DaemonMessage | None:
        remaining = max(0.0, deadline - time.monotonic())
        try:
            return self._messages.get(timeout=min(remaining, 0.1))
        except queue.Empty:
            return None

    def _handle_event(self, message: DaemonMessage) -> None:
        if message.event == "app.started":
            app_id = message.params.get("appId")
            if isinstance(app_id, str):
                self._app_id = app_id
                self._started.set()

    @staticmethod
    def _kill_process_tree(pid: int) -> None:
        try:
            root = psutil.Process(pid)
            children = root.children(recursive=True)
        except psutil.NoSuchProcess:
            return
        for child in children:
            try:
                child.kill()
            except (psutil.NoSuchProcess, psutil.AccessDenied):
                pass
        try:
            root.kill()
        except (psutil.NoSuchProcess, psutil.AccessDenied):
            pass
        gone, alive = psutil.wait_procs([*children, root], timeout=2)
        del gone
        for process in alive:
            try:
                process.kill()
            except (psutil.NoSuchProcess, psutil.AccessDenied):
                pass
