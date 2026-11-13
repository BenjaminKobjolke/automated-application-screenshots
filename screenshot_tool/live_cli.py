"""JSON-lines command loop for a long-running live screenshot session."""

from __future__ import annotations

import json
import re
import sys
from dataclasses import dataclass
from enum import Enum
from typing import TextIO

from .demo_server import ScreenInfo
from .live_gesture import parse_gesture_request
from .live_input import InputKind, InputRequest, PressKey, parse_input_request
from .live_session import (
    LiveError,
    LiveSession,
    ReloadOutcome,
    ShotOrientation,
    ShotRequest,
    ShotTheme,
)
from .visible_text import VisibleTextEntry

# BCP 47 style codes with underscores are accepted for Flutter locale names.
_LANGUAGE_CODE = re.compile(r"[A-Za-z]{2,3}([-_][A-Za-z0-9]{2,8})*")


class LiveCommand(str, Enum):
    """Commands accepted from the live-mode caller."""

    START = "start"
    RELOAD = "reload"
    SCREENS = "screens"
    SHOT = "shot"
    GESTURE = "gesture"
    READ_TEXT = InputKind.READ_TEXT.value
    TAP_TEXT = InputKind.TAP_TEXT.value
    TAP_KEY = InputKind.TAP_KEY.value
    TYPE_TEXT = InputKind.TYPE_TEXT.value
    PRESS_KEY = InputKind.PRESS_KEY.value
    RESET = "reset"
    STOP = "stop"


@dataclass(frozen=True)
class LiveReply:
    """One response and whether the command loop should continue."""

    response: dict[str, object]
    keep_going: bool


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
                reply = self.respond(line)
                self._write(reply.response)
                if not reply.keep_going:
                    break
        except KeyboardInterrupt:
            pass
        finally:
            self.stop()
        return 0

    def respond(self, line: str) -> LiveReply:
        """Handle one command and return its response without writing it."""
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
            return LiveReply(response, kind is not LiveCommand.STOP)
        except (json.JSONDecodeError, ValueError, TypeError) as error:
            response = {"ok": False, "error": str(error)}
            has_valid_request_command = (
                "request" in locals()
                and isinstance(request, dict)
                and isinstance(request.get("command"), str)
            )
            if has_valid_request_command:
                response["command"] = request["command"]
                if "id" in request:
                    response["id"] = request["id"]
            return LiveReply(response, True)
        except LiveError as error:
            response: dict[str, object] = {"ok": False, "error": error.message}
            if error.output:
                response["output"] = error.output
            if "request" in locals() and isinstance(request, dict):
                if isinstance(request.get("command"), str):
                    response["command"] = request["command"]
                if "id" in request:
                    response["id"] = request["id"]
            return LiveReply(response, True)

    def _execute(self, command: LiveCommand, request: dict[str, object]) -> dict[str, object]:
        if command is LiveCommand.STOP:
            self.stop()
            return {"ok": True}
        if command is LiveCommand.START:
            if self._started:
                raise LiveError("live session is already started")
            device = self._session.start()
            self._started = True
            return {"ok": True, "device": device}
        if not self._started:
            raise LiveError("not started")
        if command is LiveCommand.RESET:
            app_settings = request.get("app_settings")
            if "app_settings" in request and not isinstance(app_settings, dict):
                raise ValueError("app_settings must be an object")
            self._session.reset(app_settings if isinstance(app_settings, dict) else None)
            return {"ok": True}
        if command is LiveCommand.RELOAD:
            result = self._session.reload()
            succeeded = result.outcome not in {
                ReloadOutcome.COMPILE_ERROR,
                ReloadOutcome.UNRESPONSIVE,
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
        if command is LiveCommand.GESTURE:
            gesture = parse_gesture_request(request)
            self._session.gesture(gesture)
            return {"ok": True, "kind": gesture.kind.value}
        if command in {
            LiveCommand.READ_TEXT,
            LiveCommand.TAP_TEXT,
            LiveCommand.TAP_KEY,
            LiveCommand.TYPE_TEXT,
            LiveCommand.PRESS_KEY,
        }:
            input_request = parse_input_request(InputKind(command.value), request)
            event = self._session.send_input(input_request)
            return _input_response(input_request, event.entries)
        raise ValueError(f"unknown command: {command.value}")

    def _write(self, response: dict[str, object]) -> None:
        self._stdout.write(json.dumps(response, separators=(",", ":")) + "\n")
        self._stdout.flush()

    def stop(self) -> None:
        """Stop the underlying live session once."""
        if not self._stopped:
            self._stopped = True
            self._session.stop()


def _input_response(
    request: InputRequest, entries: tuple[VisibleTextEntry, ...] | None
) -> dict[str, object]:
    """Serialize a successful connector input reply for the CLI protocol."""
    if request.kind is InputKind.READ_TEXT:
        return {
            "ok": True,
            "entries": [entry.to_json() for entry in entries or ()],
        }
    if request.kind in (InputKind.TAP_TEXT, InputKind.TYPE_TEXT):
        return {"ok": True, "text": request.text}
    key = request.key.value if isinstance(request.key, PressKey) else request.key
    return {"ok": True, "key": key}


def _screen_json(screen: ScreenInfo) -> dict[str, object]:
    """Serialize the typed screen metadata for the JSON-lines protocol."""
    value: dict[str, object] = {"name": screen.name}
    if screen.description is not None:
        value["description"] = screen.description
    if screen.needs_login is not None:
        value["needs_login"] = screen.needs_login
    if screen.sections:
        value["sections"] = list(screen.sections)
    if screen.record_id is not None:
        value["record_id"] = screen.record_id
    return value


def _shot_request(request: dict[str, object]) -> ShotRequest:
    """Validate JSON shot options and convert them to the typed session request."""
    screen = request.get("screen")
    out = request.get("out")
    if "screen" in request and (not isinstance(screen, str) or not screen):
        raise ValueError("screen must be a non-empty string")
    if not isinstance(out, str):
        raise ValueError("shot requires string out field")
    if screen is None:
        for field in ("section", "record_id", "language"):
            if field in request:
                raise ValueError(f"{field} requires screen")

    theme: ShotTheme | None = None
    if "theme" in request:
        theme_value = request["theme"]
        if theme_value not in (ShotTheme.DARK.value, ShotTheme.LIGHT.value):
            raise ValueError("theme must be dark or light")
        theme = ShotTheme(theme_value)

    orientation: ShotOrientation | None = None
    if "orientation" in request:
        orientation_value = request["orientation"]
        if orientation_value not in (
            ShotOrientation.PORTRAIT.value,
            ShotOrientation.LANDSCAPE.value,
        ):
            raise ValueError("orientation must be portrait or landscape")
        orientation = ShotOrientation(orientation_value)

    section: str | None = None
    if "section" in request:
        section_value = request["section"]
        if not isinstance(section_value, str) or not section_value:
            raise ValueError("section must be a non-empty string")
        section = section_value

    full = request.get("full", False)
    if not isinstance(full, bool):
        raise ValueError("full must be a boolean")

    record_id: int | None = None
    if "record_id" in request:
        record_id_value = request["record_id"]
        if not isinstance(record_id_value, int) or isinstance(record_id_value, bool):
            raise ValueError("record_id must be an integer")
        record_id = record_id_value

    language: str | None = None
    if "language" in request:
        language_value = request["language"]
        if not isinstance(language_value, str) or _LANGUAGE_CODE.fullmatch(language_value) is None:
            raise ValueError("language must be a language code such as de or en-US")
        language = language_value

    return ShotRequest(
        screen,
        out,
        theme,
        section,
        full,
        record_id=record_id,
        language=language,
        orientation=orientation,
    )
