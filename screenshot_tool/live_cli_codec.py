"""Validate and serialize values at the live CLI's JSON boundary."""

from __future__ import annotations

import re

from .demo_server import ScreenInfo
from .live_input import InputKind, InputRequest, PressKey
from .live_session import ShotOrientation, ShotRequest, ShotTheme
from .visible_text import VisibleTextEntry

# BCP 47 style codes with underscores are accepted for Flutter locale names.
_LANGUAGE_CODE = re.compile(r"[A-Za-z]{2,3}([-_][A-Za-z0-9]{2,8})*")


def _input_response(
    request: InputRequest, entries: tuple[VisibleTextEntry, ...] | None
) -> dict[str, object]:
    """Serialize a successful connector input reply for the CLI protocol."""
    if request.kind is InputKind.READ_TEXT:
        return {"ok": True, "entries": [entry.to_json() for entry in entries or ()]}
    if request.kind in (InputKind.TAP_TEXT, InputKind.TYPE_TEXT):
        return {"ok": True, "text": request.text}
    key = request.key.value if isinstance(request.key, PressKey) else request.key
    return {"ok": True, "key": key}


def _screen_json(screen: ScreenInfo) -> dict[str, object]:
    """Serialize typed screen metadata for the JSON-lines protocol."""
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
