"""Typed live input requests and connector payloads."""

from collections.abc import Mapping
from dataclasses import dataclass
from enum import Enum

_COMMAND = "command"
_TEXT = "text"
_MATCH = "match"
_INDEX = "index"
_KEY = "key"
_FIELD = "field"


class InputKind(str, Enum):
    """Live input commands supported by the connector."""

    READ_TEXT = "read_text"
    TAP_TEXT = "tap_text"
    TAP_KEY = "tap_key"
    TYPE_TEXT = "type_text"
    PRESS_KEY = "press_key"

    @property
    def reply_event(self) -> str:
        """Return the reply event associated with this command."""
        match self:
            case InputKind.READ_TEXT:
                return "visible_text"
            case InputKind.TAP_TEXT:
                return "text_tapped"
            case InputKind.TAP_KEY:
                return "key_tapped"
            case InputKind.TYPE_TEXT:
                return "text_typed"
            case InputKind.PRESS_KEY:
                return "key_pressed"
        raise AssertionError(f"Unsupported input kind: {self}")


class TextMatch(str, Enum):
    """Matching strategy for selecting a visible text control."""

    EXACT = "exact"
    CONTAINS = "contains"


class PressKey(str, Enum):
    """Keys that the connector can press inside the app."""

    ENTER = "enter"
    TAB = "tab"
    SHIFT_TAB = "shift_tab"
    ESCAPE = "escape"
    BACKSPACE = "backspace"
    ARROW_UP = "arrow_up"
    ARROW_DOWN = "arrow_down"
    ARROW_LEFT = "arrow_left"
    ARROW_RIGHT = "arrow_right"


@dataclass(frozen=True)
class InputRequest:
    """Validated input command and its optional arguments."""

    kind: InputKind
    text: str | None = None
    match: TextMatch | None = None
    index: int | None = None
    key: str | PressKey | None = None
    field: str | None = None


def parse_input_request(kind: InputKind, data: Mapping[str, object]) -> InputRequest:
    """Validate command arguments and return their typed representation."""
    text = None
    match = None
    index = None
    key = None
    field = None

    if kind in (InputKind.TAP_TEXT, InputKind.TYPE_TEXT):
        text = _required_non_empty_string(data, _TEXT)

    if kind is InputKind.TAP_TEXT:
        if _MATCH in data:
            match_value = data[_MATCH]
            if not isinstance(match_value, str):
                raise ValueError("match must be exact or contains")
            try:
                match = TextMatch(match_value)
            except ValueError:
                raise ValueError("match must be exact or contains") from None
        if _INDEX in data:
            index_value = data[_INDEX]
            if (
                not isinstance(index_value, int)
                or isinstance(index_value, bool)
                or index_value < 0
            ):
                raise ValueError("index must be a non-negative integer")
            index = index_value

    if kind is InputKind.TAP_KEY:
        key = _required_non_empty_string(data, _KEY)

    if kind is InputKind.PRESS_KEY:
        key_value = _required_non_empty_string(data, _KEY)
        try:
            key = PressKey(key_value)
        except ValueError:
            supported = ", ".join(value.value for value in PressKey)
            raise ValueError(f"key must be one of: {supported}") from None

    if _FIELD in data:
        field = _required_non_empty_string(data, _FIELD)

    return InputRequest(
        kind=kind,
        text=text,
        match=match,
        index=index,
        key=key,
        field=field,
    )


def build_input_payload(request: InputRequest) -> dict[str, object]:
    """Build the connector command from a validated request."""
    payload: dict[str, object] = {_COMMAND: request.kind.value}
    if request.text is not None:
        payload[_TEXT] = request.text
    if request.match is not None:
        payload[_MATCH] = request.match.value
    if request.index is not None:
        payload[_INDEX] = request.index
    if request.key is not None:
        payload[_KEY] = request.key.value if isinstance(request.key, PressKey) else request.key
    if request.field is not None:
        payload[_FIELD] = request.field
    return payload


def _required_non_empty_string(data: Mapping[str, object], field: str) -> str:
    """Read a required non-empty string field from a request."""
    value = data.get(field)
    if not isinstance(value, str) or not value:
        raise ValueError(f"{field} must be a non-empty string")
    return value
