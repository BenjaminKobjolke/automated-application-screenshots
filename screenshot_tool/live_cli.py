"""JSON-lines command loop for a long-running live screenshot session."""

from __future__ import annotations

import json
import sys
from dataclasses import dataclass
from enum import Enum
from time import monotonic
from typing import TextIO

from .app_logger import AppLogger
from .live_app_link import _now
from .live_cli_codec import _input_response, _screen_json, _shot_request
from .live_gesture import parse_gesture_request
from .live_input import InputKind, parse_input_request
from .live_session import (
    LiveError,
    LiveSession,
    ReloadOutcome,
)


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
        started_at = monotonic()
        command: str | None = None
        succeeded = False
        try:
            request = json.loads(line)
            if not isinstance(request, dict):
                raise ValueError("request must be a JSON object")
            raw_command = request.get("command")
            if not isinstance(raw_command, str):
                raise ValueError("request must include a string command")
            command = raw_command
            AppLogger.info(f"Received '{command}' at {_now()}")
            try:
                kind = LiveCommand(command)
            except ValueError:
                raise ValueError(f"unknown command: {command}") from None
            response = self._execute(kind, request)
            _copy_request_metadata(response, request)
            succeeded = response.get("ok") is True
            return LiveReply(response, kind is not LiveCommand.STOP)
        except (json.JSONDecodeError, ValueError, TypeError) as error:
            response = {"ok": False, "error": str(error)}
            if "request" in locals() and isinstance(request, dict):
                _copy_request_metadata(response, request)
            return LiveReply(response, True)
        except LiveError as error:
            response: dict[str, object] = {"ok": False, "error": error.message}
            if error.output:
                response["output"] = error.output
            if "request" in locals() and isinstance(request, dict):
                _copy_request_metadata(response, request)
            return LiveReply(response, True)
        except Exception as error:
            AppLogger.error(
                f"Unexpected live command error: {type(error).__name__}: {error}"
            )
            response = {
                "ok": False,
                "error": f"{type(error).__name__}: {error}",
            }
            if "request" in locals() and isinstance(request, dict):
                _copy_request_metadata(response, request)
            return LiveReply(response, True)
        finally:
            if command is not None:
                duration = max(monotonic() - started_at, 0.0)
                result = "succeeded" if succeeded else "failed"
                message = f"Live command '{command}' {result} in {duration:.1f}s"
                if succeeded:
                    AppLogger.info(message)
                else:
                    AppLogger.error(message)
                    if command not in {LiveCommand.START.value, LiveCommand.STOP.value}:
                        try:
                            state = self._session.device_state()
                            if state:
                                AppLogger.warning(f"Android device state: {state}")
                        except Exception as state_error:
                            AppLogger.error(
                                "Could not read Android device state: "
                                f"{type(state_error).__name__}: {state_error}"
                            )

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


def _copy_request_metadata(
    response: dict[str, object], request: dict[str, object]
) -> None:
    """Echo the command and optional correlation id in every parsed reply."""
    command = request.get("command")
    if isinstance(command, str):
        response["command"] = command
    if "id" in request:
        response["id"] = request["id"]
