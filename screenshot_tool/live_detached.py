"""Manage one-shot control calls to a detached Flutter live session."""

from __future__ import annotations

import json
import os
import secrets
import subprocess
import sys
import time
from contextlib import suppress
from pathlib import Path
from typing import TextIO

import psutil

from .live_cli import LiveCLI
from .live_config import LiveSettings, LiveTarget
from .live_control import ControlServer, SessionFile, SessionGone, send_line
from .live_session import LiveSession
from .process_tree import kill_process_tree

_POLL_SECONDS = 0.05
_SESSION_FILE_TIMEOUT = 10.0
_SERVER_MODULE = "screenshot_tool.live_detached"
_ANDROID_START_STAGES = 4
_OTHER_START_STAGES = 2
_START_REPLY_MARGIN_SECONDS = 60


def start(
    folder: str | Path, settings: LiveSettings, output: TextIO | None = None
) -> int:
    """Start a detached live session and print its successful start reply."""
    directory = Path(folder).expanduser().resolve()
    session = SessionFile.read(directory)
    if session is not None and _is_server_process(session.pid):
        return _write_response(
            {"ok": False, "error": f"a live session already exists in {directory}"}, output, 1
        )
    SessionFile.remove(directory)
    directory.mkdir(parents=True, exist_ok=True)
    log_path = directory / "live.log"
    command = [sys.executable, "-m", _SERVER_MODULE, "--serve", str(directory)]
    process: subprocess.Popen[bytes] | None = None
    try:
        with log_path.open("ab") as log:
            process = _spawn_server(command, Path.cwd(), log)
            if process.stdin is None:
                raise OSError("detached server settings pipe was not created")
            process.stdin.write(
                json.dumps(_settings_data(settings), separators=(",", ":")).encode("utf-8")
                + b"\n"
            )
            process.stdin.close()
        deadline = time.monotonic() + _SESSION_FILE_TIMEOUT
        while time.monotonic() < deadline:
            session = SessionFile.read(directory)
            if session is not None:
                break
            if process.poll() is not None:
                raise SessionGone("live session server exited before becoming ready")
            time.sleep(_POLL_SECONDS)
        else:
            raise SessionGone("timed out waiting for the live session server to become ready")

        response = send_line(
            directory, '{"command":"start"}', timeout=start_reply_timeout(settings)
        )
        if response.get("ok") is True:
            return _write_response(response, output, 0)
        _stop_or_kill(directory, session)
        return _write_response(response, output, 1)
    except (OSError, SessionGone, ValueError) as error:
        if process is not None:
            with suppress(Exception):
                kill_process_tree(process.pid)
        SessionFile.remove(directory)
        return _write_response({"ok": False, "error": str(error)}, output, 1)


def send(folder: str | Path, line: str, output: TextIO | None = None) -> int:
    """Send one JSON-lines command and map its response to the CLI exit code."""
    try:
        response = send_line(folder, line)
    except SessionGone as error:
        return _write_response({"ok": False, "error": str(error)}, output, 3)
    return _write_response(response, output, 0 if response.get("ok") is True else 1)


def start_reply_timeout(settings: LiveSettings) -> float:
    """Allow one timeout per bounded startup stage, plus the existing margin."""
    # Android adds adb serial and emulator boot waits before Flutter and app connection/reset.
    stages = (
        _ANDROID_START_STAGES
        if settings.target is LiveTarget.ANDROID_EMULATOR
        else _OTHER_START_STAGES
    )
    return float(settings.start_timeout * stages + _START_REPLY_MARGIN_SECONDS)


def stop(folder: str | Path, output: TextIO | None = None) -> int:
    """Stop a session, falling back to guarded process-tree cleanup."""
    session = SessionFile.read(folder)
    if session is None:
        SessionFile.remove(folder)
        return _write_response({"ok": True, "stopped": False}, output, 0)
    try:
        response = send_line(folder, '{"command":"stop"}')
        if response.get("ok") is True:
            SessionFile.remove(folder)
            return _write_response({"ok": True, "stopped": True}, output, 0)
    except SessionGone:
        pass
    _stop_or_kill(folder, session)
    SessionFile.remove(folder)
    return _write_response({"ok": True, "stopped": True}, output, 0)


def serve(folder: str | Path, settings: LiveSettings) -> int:
    """Run the background live session and its authenticated control server."""
    directory = Path(folder)
    directory.mkdir(parents=True, exist_ok=True)
    server = ControlServer()
    token = secrets.token_urlsafe(32)
    timeout = float(settings.start_timeout) + 60.0
    SessionFile(server.port, token, os.getpid(), timeout).write(directory)
    cli = LiveCLI(LiveSession(settings), sys.stdin, sys.stdout)
    try:
        server.serve(cli, token)
    finally:
        cli.stop()
        SessionFile.remove(directory)
        server.close()
    return 0


def _stop_or_kill(folder: str | Path, session: SessionFile) -> None:
    try:
        send_line(folder, '{"command":"stop"}')
    except SessionGone:
        pass
    if _is_server_process(session.pid):
        kill_process_tree(session.pid)
    SessionFile.remove(folder)


def _is_server_process(pid: int) -> bool:
    """Only kill a pid whose command line identifies our detached server."""
    try:
        command = psutil.Process(pid).cmdline()
    except (psutil.NoSuchProcess, psutil.AccessDenied):
        return False
    return "-m" in command and _SERVER_MODULE in command and "--serve" in command


def _spawn_server(
    command: list[str], working_directory: Path, log: TextIO
) -> subprocess.Popen[bytes]:
    options: dict[str, object] = {
        "args": command,
        "cwd": working_directory,
        "stdin": subprocess.PIPE,
        "stdout": log,
        "stderr": subprocess.STDOUT,
        "close_fds": True,
    }
    if sys.platform == "win32":
        flags = subprocess.CREATE_NO_WINDOW | subprocess.CREATE_NEW_PROCESS_GROUP
        try:
            return subprocess.Popen(**options, creationflags=flags)
        except OSError:
            return subprocess.Popen(**options, creationflags=subprocess.CREATE_NO_WINDOW)
    return subprocess.Popen(**options, start_new_session=True)


def _settings_data(settings: LiveSettings) -> dict[str, object]:
    return {
        "target": settings.target.value,
        "port": settings.port,
        "avd": settings.avd,
        "devices": settings.devices,
        "headless": settings.headless,
        "flutter": list(settings.flutter),
        "run_args": list(settings.run_args),
        "project_dir": str(settings.project_dir),
        "app_settings": settings.app_settings,
        "start_timeout": settings.start_timeout,
    }


def _settings_from_data(value: str) -> LiveSettings:
    data = json.loads(value)
    if not isinstance(data, dict):
        raise ValueError("invalid detached live settings")
    return LiveSettings(
        target=LiveTarget(data["target"]),
        port=data["port"],
        avd=data["avd"],
        devices=data["devices"],
        headless=data["headless"],
        flutter=tuple(data["flutter"]),
        run_args=tuple(data["run_args"]),
        project_dir=Path(data["project_dir"]),
        app_settings=data["app_settings"],
        start_timeout=data["start_timeout"],
    )


def _write_response(
    response: dict[str, object], output: TextIO | None, exit_code: int
) -> int:
    stream = output if output is not None else sys.stdout
    stream.write(json.dumps(response, separators=(",", ":")) + "\n")
    stream.flush()
    return exit_code


def _main() -> int:
    if len(sys.argv) != 3 or sys.argv[1] != "--serve":
        return 2
    try:
        settings_line = sys.stdin.readline()
        if not settings_line:
            raise ValueError("detached live settings were not provided")
        settings = _settings_from_data(settings_line)
        return serve(sys.argv[2], settings)
    except Exception as error:
        sys.stderr.write(f"detached live session failed: {error}\n")
        return 1


if __name__ == "__main__":
    raise SystemExit(_main())
