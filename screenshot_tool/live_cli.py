"""JSON-lines command loop for a long-running live screenshot session."""

from __future__ import annotations

import json
import sys
from enum import Enum
from typing import TextIO

from .demo_server import ScreenInfo
from .live_session import LiveError, LiveSession, ReloadOutcome, ShotRequest, ShotTheme


class LiveCommand(str, Enum):
    """Commands accepted from the live-mode caller."""

    START = "start"
    RELOAD = "reload"
    SCREENS = "screens"
    SHOT = "shot"
    STOP = "stop"


class LiveCLI:
    """Read JSON commands and write one JSON response for each input line."""

    def __init__(
        self,
        session: LiveSession,
        stdin: TextIO = sys.stdin,
        stdout: TextIO = sys.stdout,
    ) -> None:
        self._session = session
        self._stdin = stdin
        self._stdout = stdout
        self._started = False
        self._stopped = False

    def run(self) -> int:
        """Serve commands until stop, EOF, or Ctrl+C; always clean up the session."""
        try:
            for line in self._stdin:
                if not self._dispatch(line):
                    break
        except KeyboardInterrupt:
            pass
        finally:
            self._stop()
        return 0

    def _dispatch(self, line: str) -> bool:
        try:
            request = json.loads(line)
            if not isinstance(request, dict):
                raise ValueError("request must be a JSON object")
            command = request.get("command")
            if not isinstance(command, str):
                raise ValueError("request must include a string command")
            try:
                kind = LiveCommand(command)
            except ValueError:
                raise ValueError(f"unknown command: {command}") from None
            response = self._execute(kind, request)
            response["command"] = command
            if "id" in request:
                response["id"] = request["id"]
            self._write(response)
            return kind is not LiveCommand.STOP
        except (json.JSONDecodeError, ValueError, TypeError) as error:
            response = {"ok": False, "error": str(error)}
            if (
                "request" in locals()
                and isinstance(request, dict)
                and isinstance(request.get("command"), str)
            ):
                response["command"] = request["command"]
                if "id" in request:
                    response["id"] = request["id"]
            self._write(response)
        except LiveError as error:
            response: dict[str, object] = {"ok": False, "error": error.message}
            if error.output:
                response["output"] = error.output
            if "request" in locals() and isinstance(request, dict):
                if isinstance(request.get("command"), str):
                    response["command"] = request["command"]
                if "id" in request:
                    response["id"] = request["id"]
            self._write(response)
        return True

    def _execute(self, command: LiveCommand, request: dict[str, object]) -> dict[str, object]:
        if command is LiveCommand.STOP:
            self._stop()
            return {"ok": True}
        if command is LiveCommand.START:
            if self._started:
                raise LiveError("live session is already started")
            device = self._session.start()
            self._started = True
            return {"ok": True, "device": device}
        if not self._started:
            raise LiveError("not started")
        if command is LiveCommand.RELOAD:
            result = self._session.reload()
            succeeded = result.outcome not in {
                ReloadOutcome.COMPILE_ERROR,
                ReloadOutcome.FAILED,
            }
            return {
                "ok": succeeded,
                "result": result.outcome.value,
                "message": result.message,
                "output": result.output,
            }
        if command is LiveCommand.SCREENS:
            return {
                "ok": True,
                "screens": [_screen_json(screen) for screen in self._session.screens()],
            }
        if command is LiveCommand.SHOT:
            path = self._session.shot(_shot_request(request))
            return {"ok": True, "path": str(path)}
        raise ValueError(f"unknown command: {command.value}")

    def _write(self, response: dict[str, object]) -> None:
        self._stdout.write(json.dumps(response, separators=(",", ":")) + "\n")
        self._stdout.flush()

    def _stop(self) -> None:
        if not self._stopped:
            self._stopped = True
            self._session.stop()


def _screen_json(screen: ScreenInfo) -> dict[str, object]:
    """Serialize the typed screen metadata for the JSON-lines protocol."""
    value: dict[str, object] = {"name": screen.name}
    if screen.description is not None:
        value["description"] = screen.description
    if screen.needs_login is not None:
        value["needs_login"] = screen.needs_login
    if screen.sections:
        value["sections"] = list(screen.sections)
    return value


def _shot_request(request: dict[str, object]) -> ShotRequest:
    """Validate JSON shot options and convert them to the typed session request."""
    screen = request.get("screen")
    out = request.get("out")
    if not isinstance(screen, str) or not isinstance(out, str):
        raise ValueError("shot requires string screen and out fields")

    theme: ShotTheme | None = None
    if "theme" in request:
        theme_value = request["theme"]
        if theme_value not in (ShotTheme.DARK.value, ShotTheme.LIGHT.value):
            raise ValueError("theme must be dark or light")
        theme = ShotTheme(theme_value)

    section: str | None = None
    if "section" in request:
        section_value = request["section"]
        if not isinstance(section_value, str) or not section_value:
            raise ValueError("section must be a non-empty string")
        section = section_value

    full = request.get("full", False)
    if not isinstance(full, bool):
        raise ValueError("full must be a boolean")

    return ShotRequest(screen, out, theme, section, full)
