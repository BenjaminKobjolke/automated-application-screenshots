"""Typed gesture requests and connector payloads for live sessions."""

from collections.abc import Mapping
from dataclasses import dataclass
from enum import Enum
from math import isfinite

_COMMAND = "command"
_GESTURE = "gesture"
_KIND = "kind"
_AT = "at"
_FROM = "from"
_TO = "to"
_CENTER = "center"
_SCALE = "scale"
_DURATION_MS = "duration_ms"
_SCREEN = "screen"
_SECTION = "section"


class GestureKind(str, Enum):
    """Gesture actions supported by the live connector."""

    TAP = "tap"
    DRAG = "drag"
    PINCH = "pinch"


_POINT_FIELDS = {
    GestureKind.TAP: (_AT,),
    GestureKind.DRAG: (_FROM, _TO),
    GestureKind.PINCH: (_CENTER,),
}


@dataclass(frozen=True)
class GestureRequest:
    """Validated points and options for one live gesture."""

    kind: GestureKind
    at: tuple[float, float] | None = None
    from_point: tuple[float, float] | None = None
    to: tuple[float, float] | None = None
    center: tuple[float, float] | None = None
    scale: float | None = None
    duration_ms: int | None = None
    screen: str | None = None
    section: str | None = None


def parse_gesture_request(data: Mapping[str, object]) -> GestureRequest:
    """Validate a JSON gesture request and return its typed representation."""
    kind_value = data.get(_KIND)
    if not isinstance(kind_value, str):
        raise ValueError("kind must be tap, drag or pinch")
    try:
        kind = GestureKind(kind_value)
    except ValueError:
        raise ValueError("kind must be tap, drag or pinch") from None

    points: dict[str, tuple[float, float]] = {}
    for field in _POINT_FIELDS[kind]:
        points[field] = _parse_point(data, field)

    scale = None
    if kind is GestureKind.PINCH:
        scale_value = data.get(_SCALE)
        if not isinstance(scale_value, (int, float)) or isinstance(scale_value, bool):
            raise ValueError("scale must be a positive number")
        try:
            scale = float(scale_value)
        except OverflowError:
            raise ValueError("scale must be a positive number") from None
        if not isfinite(scale) or not scale > 0:
            raise ValueError("scale must be a positive number")

    duration_ms = None
    if _DURATION_MS in data:
        duration_value = data[_DURATION_MS]
        if (
            not isinstance(duration_value, int)
            or isinstance(duration_value, bool)
            or duration_value <= 0
        ):
            raise ValueError("duration_ms must be a positive integer")
        duration_ms = duration_value

    screen = _optional_non_empty_string(data, _SCREEN)
    section = _optional_non_empty_string(data, _SECTION)
    if section is not None and screen is None:
        raise ValueError("section requires screen")

    return GestureRequest(
        kind=kind,
        at=points.get(_AT),
        from_point=points.get(_FROM),
        to=points.get(_TO),
        center=points.get(_CENTER),
        scale=scale,
        duration_ms=duration_ms,
        screen=screen,
        section=section,
    )


def build_gesture_payload(request: GestureRequest) -> dict[str, object]:
    """Build the connector command from a validated gesture request."""
    payload: dict[str, object] = {_COMMAND: _GESTURE, _KIND: request.kind.value}
    for field in _POINT_FIELDS[request.kind]:
        point = getattr(request, "from_point" if field == _FROM else field)
        if point is not None:
            payload[field] = list(point)
    if request.scale is not None:
        payload[_SCALE] = request.scale
    if request.duration_ms is not None:
        payload[_DURATION_MS] = request.duration_ms
    if request.screen is not None:
        payload[_SCREEN] = request.screen
    if request.section is not None:
        payload[_SECTION] = request.section
    return payload


def _parse_point(data: Mapping[str, object], field: str) -> tuple[float, float]:
    """Parse one point expressed as two normalized coordinates."""
    value = data.get(field)
    if not isinstance(value, list) or len(value) != 2:
        raise ValueError(f"{field} must be a list of two coordinates")
    if any(
        not isinstance(coordinate, (int, float)) or isinstance(coordinate, bool)
        for coordinate in value
    ):
        raise ValueError(f"{field} coordinates must be numbers")
    x, y = value
    if not (0 <= x <= 1 and 0 <= y <= 1):
        raise ValueError(f"{field} coordinates must be between 0 and 1")
    return float(x), float(y)


def _optional_non_empty_string(data: Mapping[str, object], field: str) -> str | None:
    if field not in data:
        return None
    value = data[field]
    if not isinstance(value, str) or not value:
        raise ValueError(f"{field} must be a non-empty string")
    return value
