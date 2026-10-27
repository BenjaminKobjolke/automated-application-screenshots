"""Typed configuration models shared by the config parsers."""

from dataclasses import dataclass, field
from typing import Any

from .live_config import LiveSettings
from .web_config import WebSettings

DEFAULT_PIXEL_RATIO = 1.0
ACCEPT_TIMEOUT_S = 30.0
_FIT_KNOBS = {
    "tour": ("crf", "width", "fps"),
    "stills_gif": ("lossy", "colors", "width"),
    "mp4_gif": ("lossy", "colors", "fps", "width"),
}


@dataclass(frozen=True)
class LaunchSettings:
    """How to start the target application for a demo run."""

    command: tuple[str, ...]
    cwd: str | None
    # Environment for the child, with {temp}/{demo_id}/{name}/{lang} expanded.
    # Enough on its own to point an app at a throwaway profile without a
    # wrapper script.
    env: tuple[tuple[str, str], ...] = ()
    # The tool runs under uv, whose virtualenv is first on the child's PATH and
    # holds none of the app's dependencies. Set true only if the app really
    # wants the tool's environment.
    inherit_env: bool = False
    # Clear the desktop before the app starts; see WindowStacking.minimize_all.
    minimize_all: bool = True


@dataclass(frozen=True)
class NetworkSettings:
    """Network demo mode: the tool listens, a phone/emulator app connects.

    The app records video itself and uploads it; nothing is launched here.
    """

    port: int

    # How long to wait for the app to connect. The default suits a device that
    # is already up; a run that first boots an emulator and builds the app
    # needs minutes, so those configs raise it.
    accept_timeout: float = ACCEPT_TIMEOUT_S


@dataclass(frozen=True)
class VerifyCheck:
    """Evidence that a demo actually did what its script says it does.

    A demo can play to the end, report every event and still have missed - a
    dialog stole a keystroke, a viewer never took focus. Checking the side
    effect is the difference between a green run and a correct one.
    """

    kind: str
    path: str
    text: str | None = None

    def describe(self) -> str:
        if self.kind == "contains":
            return f"{self.path} contains {self.text!r}"
        return f"{self.path} exists"


@dataclass(frozen=True)
class DemoSpec:
    """One recordable demo the target application can play."""

    id: int
    name: str
    fps: int = 10
    formats: tuple[str, ...] = ("gif",)
    width: int | None = None
    height: int | None = None
    # Opaque app-specific settings, written to a JSON file the app receives
    # via --automation-demo-settings
    app_settings: tuple[tuple[str, str], ...] = ()
    # Record once per language ("en", "de", ...); empty = one run, no lang folder
    languages: tuple[str, ...] = ()
    # Pixels removed from each captured frame, (top, right, bottom, left).
    # For residual edge cleanup after the DWM/work-area capture bounds.
    crop: tuple[int, int, int, int] = (0, 0, 0, 0)
    # Side effects that prove the demo landed, checked after it ends.
    verify: tuple[VerifyCheck, ...] = ()
    # Which compose step this demo feeds ("tour", "feature", ...). Replaces
    # matching on a name prefix, which no config could state and every
    # post-processing script had to re-implement.
    group: str | None = None
    # Title a "tour" compose step burns over this chapter; captions holds the
    # per-language wording, caption the single-language case.
    caption: str | None = None
    captions: tuple[tuple[str, str], ...] = ()
    # Network mode: device pixel ratio for in-app stills (1.0 = logical pixels).
    pixel_ratio: float = DEFAULT_PIXEL_RATIO
    # Web mode starts a demo at this application-relative path.
    path: str = "/"
    # Network mode: steps sent to the app verbatim instead of a demo registered
    # in the app (see the connector's docs/WRITING_DEMOS.md for the shape).
    steps: tuple[dict[str, Any], ...] = ()

    @property
    def wants_video(self) -> bool:
        """Whether a network-mode app must screen-record this demo."""
        return "gif" in self.formats or "mp4" in self.formats

    @property
    def short_name(self) -> str:
        """The name without its group prefix: "feature-goto" -> "goto".

        Now that the group is a config field, the prefix in the name is
        redundant - but it is also what the published files are called, so
        {short} in a compose output keeps those filenames.
        """
        prefix = f"{self.group}-"
        return (
            self.name[len(prefix) :] if self.group and self.name.startswith(prefix) else self.name
        )

    def caption_for(self, language: str | None) -> str | None:
        """This demo's caption in ``language``, falling back to ``caption``."""
        if language is not None:
            for code, text in self.captions:
                if code == language:
                    return text
        return self.caption


@dataclass(frozen=True)
class ComposeStep:
    """One post-recording artifact: what to join, how, and how big it may be."""

    type: str
    output: str
    # Inputs: a demo group (every matching demo, in id order) or one demo name.
    group: str | None = None
    demo: str | None = None
    # Type-specific encoder settings (width, fps, colors, hold, captions...).
    options: tuple[tuple[str, Any], ...] = ()
    # Size budget in bytes, and the knobs the search may move to reach it.
    # Anything not in fit is a constraint. Empty fit = check and warn only.
    max_size: int | None = None
    fit: tuple[str, ...] | None = None
    on_miss: str = "warn"

    @property
    def settings(self) -> dict[str, Any]:
        """The options as a plain dict, for the encoder."""
        return dict(self.options)

    @property
    def fit_knobs(self) -> tuple[str, ...]:
        """The knobs the size search may move, defaulted per step type."""
        return _FIT_KNOBS[self.type] if self.fit is None else self.fit


@dataclass(frozen=True)
class Settings:
    """Typed app configuration; the one object all modules read from."""

    process_name: str
    title_substring: str
    output_dir: str
    dropdown_relative_pos: tuple[int, int] | None = None
    screenshot_filename: str | None = None
    delay_after_change: float | None = None
    language_names: dict[str, str] | None = None
    launch: LaunchSettings | None = None
    network: NetworkSettings | None = None
    live: LiveSettings | None = None
    web: WebSettings | None = None
    demos: tuple[DemoSpec, ...] = ()
    compose: tuple[ComposeStep, ...] = ()
    # Folder with per-language demo text files (<texts_dir>/<lang>.json)
    texts_dir: str | None = None
    pause_fancyzones: bool = True
    language_codes: list[str] = field(init=False)
    name_to_code: dict[str, str] = field(init=False)

    def __post_init__(self) -> None:
        # Derived, not passed in: codes and reverse lookup always match language_names
        names = self.language_names or {}
        object.__setattr__(self, "language_codes", sorted(names))
        object.__setattr__(self, "name_to_code", {name: code for code, name in names.items()})

    def demos_in_group(self, group: str) -> tuple[DemoSpec, ...]:
        """The demos of ``group``, in id order - which is chapter order."""
        return tuple(sorted((d for d in self.demos if d.group == group), key=lambda d: d.id))

    def demo_named(self, name: str) -> DemoSpec | None:
        return next((d for d in self.demos if d.name == name), None)
