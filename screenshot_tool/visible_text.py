"""Typed visible-text entries returned by live connector commands."""

import math
from dataclasses import dataclass
from enum import Enum


class VisibleTextKind(str, Enum):
    """Kinds of visible text understood by the screenshot tool."""

    TEXT = "text"
    BUTTON = "button"
    TEXT_FIELD = "text_field"


@dataclass(frozen=True)
class VisibleTextEntry:
    """One text-bearing or tappable item visible in the app view."""

    text: str
    kind: VisibleTextKind
    enabled: bool
    bounds: tuple[float, float, float, float]
    label: str | None = None
    hint: str | None = None
    value: str | None = None

    def to_json(self) -> dict[str, object]:
        """Serialize the entry, leaving absent optional values out."""
        result: dict[str, object] = {
            "text": self.text,
            "kind": self.kind.value,
            "enabled": self.enabled,
            "bounds": list(self.bounds),
        }
        for name in ("label", "hint", "value"):
            optional_value = getattr(self, name)
            if optional_value is not None:
                result[name] = optional_value
        return result


def parse_visible_text(value: object) -> tuple[VisibleTextEntry, ...]:
    """Validate visible-text JSON entries and skip kinds this version does not know."""
    if not isinstance(value, list):
        raise ValueError("visible text entries must be a list")

    entries: list[VisibleTextEntry] = []
    for item in value:
        if not isinstance(item, dict):
            raise ValueError("visible text entry must be an object")
        kind_value = item.get("kind")
        if not isinstance(kind_value, str):
            raise ValueError("visible text kind must be a string")
        try:
            kind = VisibleTextKind(kind_value)
        except ValueError:
            continue

        text = item.get("text")
        enabled = item.get("enabled")
        bounds = item.get("bounds")
        if not isinstance(text, str):
            raise ValueError("visible text text must be a string")
        if not isinstance(enabled, bool):
            raise ValueError("visible text enabled must be a boolean")
        if (
            not isinstance(bounds, list)
            or len(bounds) != 4
            or any(
                not isinstance(coordinate, (int, float))
                or isinstance(coordinate, bool)
                or not math.isfinite(coordinate)
                or not 0 <= coordinate <= 1
                for coordinate in bounds
            )
        ):
            raise ValueError("visible text bounds must contain four fractions between 0 and 1")
        left, top, right, bottom = bounds
        if left > right or top > bottom:
            raise ValueError("visible text bounds must be ordered left, top, right, bottom")

        optional: dict[str, str | None] = {}
        for name in ("label", "hint", "value"):
            field_value = item.get(name)
            if name in item and not isinstance(field_value, str):
                raise ValueError(f"visible text {name} must be a string")
            optional[name] = field_value

        entries.append(
            VisibleTextEntry(
                text=text,
                kind=kind,
                enabled=enabled,
                bounds=(float(left), float(top), float(right), float(bottom)),
                **optional,
            )
        )
    return tuple(entries)
