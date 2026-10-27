"""Typed messages and JSON-line helpers for Flutter's machine protocol."""

import json
from dataclasses import dataclass
from typing import Any


def encode_request(request: dict[str, Any]) -> str:
    """Encode a daemon request in the array wrapper Flutter expects."""
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
    timed_out: bool = False


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
