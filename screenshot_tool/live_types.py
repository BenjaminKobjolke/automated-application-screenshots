"""Value types and app command payloads for live screenshot sessions."""

from dataclasses import dataclass
from enum import Enum
from pathlib import Path


class LiveError(RuntimeError):
    """A live-session operation failed, with relevant build output if present."""

    def __init__(self, message: str, output: str = "") -> None:
        super().__init__(message)
        self.message = message
        self.output = output


class ReloadOutcome(Enum):
    """The level of Flutter restart needed to apply the current source."""

    RELOADED = "reloaded"
    RESTARTED = "restarted"
    RELAUNCHED = "relaunched"
    COMPILE_ERROR = "compile_error"
    UNRESPONSIVE = "unresponsive"
    FAILED = "failed"


@dataclass(frozen=True)
class ReloadResult:
    """Typed outcome returned by a live reload request."""

    outcome: ReloadOutcome
    message: str = ""
    output: str = ""


class ShotTheme(str, Enum):
    """Theme requested for one live screenshot."""

    DARK = "dark"
    LIGHT = "light"


@dataclass(frozen=True)
class ShotRequest:
    """Options for capturing a named live screen."""

    screen: str
    out: str | Path
    theme: ShotTheme | None = None
    section: str | None = None
    full: bool = False
    record_id: int | None = None
    language: str | None = None

    def __post_init__(self) -> None:
        if self.section is not None and self.full:
            raise ValueError("section and full cannot be combined")

    def save_png(self, png: bytes) -> Path:
        """Save the captured PNG, creating its parent directory when needed."""
        path = Path(self.out)
        try:
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_bytes(png)
        except OSError as error:
            raise LiveError(f"could not write screenshot {path}: {error}") from error
        return path


def build_navigation_payload(request: ShotRequest) -> dict[str, object]:
    """Build the app command that navigates to the requested screen state."""
    payload: dict[str, object] = {"command": "navigate", "screen": request.screen}
    if request.section is not None:
        payload["section"] = request.section
    if request.record_id is not None:
        payload["record_id"] = request.record_id
    if request.language is not None:
        payload["language"] = request.language
    return payload


def build_screenshot_payload(request: ShotRequest) -> dict[str, object]:
    """Build the app command that captures the requested screen."""
    payload: dict[str, object] = {
        "command": "screenshot",
        "name": request.screen,
        "pixel_ratio": 1.0,
    }
    if request.full:
        payload["full"] = True
    return payload
