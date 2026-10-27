"""Typed events and parsing for the app's demo protocol."""

import base64
import json
from dataclasses import dataclass

KNOWN_EVENTS = (
    "demo_started",
    "screenshot",
    "demo_ended",
    "video",
    "error",
    "screens",
    "navigated",
    "theme_set",
    "reset_done",
)


@dataclass(frozen=True)
class ScreenInfo:
    """Typed metadata for one screen registered by the app's live connector."""

    name: str
    description: str | None = None
    needs_login: bool | None = None
    sections: tuple[str, ...] = ()
    record_id: str | None = None  # What a record id means, e.g. "todo id"; None if unsupported.


@dataclass(frozen=True)
class DemoEvent:
    """One typed event received from the target application."""

    event: str
    demo: int | None
    name: str | None
    hwnd: int | None
    # Network mode: the still itself (the phone has no window to capture)
    png: bytes | None = None
    # Network mode: byte count of the mp4 that follows a ``video`` header
    size: int | None = None
    message: str | None = None
    screens: tuple[ScreenInfo, ...] | None = None
    screen: str | None = None


def parse_event_line(line: str) -> DemoEvent:
    """Parse one protocol line into a DemoEvent.

    Raises:
        ValueError: If the line is not JSON or lacks a known 'event' key.
    """
    try:
        data = json.loads(line)
    except json.JSONDecodeError as e:
        raise ValueError(f"not JSON: {line!r}") from e
    if not isinstance(data, dict) or data.get("event") not in KNOWN_EVENTS:
        raise ValueError(f"unknown demo event: {line!r}")
    screens_data = data.get("screens")
    if "screens" in data and not isinstance(screens_data, list):
        raise ValueError("screens metadata must be a list")
    screens = None
    if isinstance(screens_data, list):
        parsed_screens: list[ScreenInfo] = []
        for item in screens_data:
            if not isinstance(item, dict) or not isinstance(item.get("name"), str):
                raise ValueError("screen metadata requires a string name")
            description = item.get("description")
            needs_login = item.get("needs_login")
            sections = item.get("sections", [])
            record_id = item.get("record_id")
            if description is not None and not isinstance(description, str):
                raise ValueError("screen description must be a string")
            if needs_login is not None and not isinstance(needs_login, bool):
                raise ValueError("screen needs_login must be a boolean")
            if record_id is not None and not isinstance(record_id, str):
                raise ValueError("screen record_id must be a string")
            if not isinstance(sections, list) or any(not isinstance(section, str) for section in sections):
                raise ValueError("screen sections must be a list of strings")
            parsed_screens.append(
                ScreenInfo(
                    item["name"], description, needs_login, tuple(sections), record_id=record_id
                )
            )
        screens = tuple(parsed_screens)
    return DemoEvent(
        event=data["event"],
        demo=data.get("demo"),
        name=data.get("name"),
        hwnd=data.get("hwnd"),
        png=base64.b64decode(data["png"]) if isinstance(data.get("png"), str) else None,
        size=data.get("size"),
        message=data.get("message"),
        screens=screens,
        screen=data.get("screen"),
    )
