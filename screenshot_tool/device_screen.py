"""Read and control the visible Android device screen through adb."""

from __future__ import annotations

import re
import subprocess
import xml.etree.ElementTree as ET
from dataclasses import dataclass
from typing import Any, Protocol

from screenshot_tool.emulator_rotation import parse_display_rotation, parse_wm_size
from screenshot_tool.live_input import TextMatch
from screenshot_tool.live_types import LiveError

_PNG_SIGNATURE = b"\x89PNG\r\n\x1a\n"
_DEFAULT_SWIPE_DURATION_MS = 300
_DUMP_PATH = "/sdcard/window_dump.xml"
_ACTIVITY_PATTERN = re.compile(
    r"ActivityRecord\{[^}]*?\bu\d+\s+([A-Za-z0-9_.]+)/[^\s}]+"
)
_BOUNDS_PATTERN = re.compile(r"\[(\d+),(\d+)\]\[(\d+),(\d+)\]")


class CommandRunner(Protocol):
    """Subprocess interface used for text and binary adb commands."""

    def run(self, args: list[str], **kwargs: Any) -> subprocess.CompletedProcess[Any]: ...


@dataclass(frozen=True)
class TextNode:
    """Visible label and device-pixel center of one Android UI node."""

    label: str
    center: tuple[int, int]


def parse_foreground_package(output: str) -> str | None:
    """Extract the package from a resumed activity in ``dumpsys activity`` output."""
    for line in output.splitlines():
        if not any(
            marker in line
            for marker in ("topResumedActivity=", "mResumedActivity:", "ResumedActivity:")
        ):
            continue
        match = _ACTIVITY_PATTERN.search(line)
        if match is not None:
            return match.group(1)
    return None


def find_text_node(
    xml: str,
    text: str,
    match: TextMatch | None,
    index: int | None,
) -> TextNode:
    """Find one UI node by its text/content description and return its center."""
    try:
        root = ET.fromstring(xml)
    except ET.ParseError as error:
        raise LiveError(f"Could not read Android UI hierarchy: {error}") from error

    visible: list[tuple[str, tuple[int, int]]] = []
    matched: list[TextNode] = []
    strategy = match or TextMatch.EXACT
    for element in root.iter():
        text_label = element.attrib.get("text", "")
        content_description = element.attrib.get("content-desc", "")
        label = text_label or content_description
        if not label:
            continue
        bounds = _BOUNDS_PATTERN.fullmatch(element.attrib.get("bounds", ""))
        if bounds is None:
            continue
        left, top, right, bottom = (int(value) for value in bounds.groups())
        center = ((left + right) // 2, (top + bottom) // 2)
        visible.append((label, center))
        candidates = (text_label, content_description)
        is_match = any(
            candidate == text if strategy is TextMatch.EXACT else text in candidate
            for candidate in candidates
            if candidate
        )
        if is_match:
            matched.append(TextNode(label, center))

    if index is not None:
        if index >= len(matched):
            raise LiveError(_not_found_message(text, visible))
        return matched[index]
    if not matched:
        raise LiveError(_not_found_message(text, visible))
    if len(matched) > 1:
        labels = ", ".join(f'"{node.label}"' for node in matched[:10])
        raise LiveError(f'Multiple Android UI nodes match "{text}": {labels}; provide index')
    return matched[0]


def _not_found_message(text: str, visible: list[tuple[str, tuple[int, int]]]) -> str:
    """Describe a missing label and the visible labels available to the caller."""
    labels = ", ".join(f'"{label}"' for label, _ in visible[:10]) or "none"
    return f'No Android UI node matches "{text}". Visible labels: {labels}'


class DeviceScreen:
    """Capture or drive the full Android screen without involving the app connector."""

    def __init__(self, runner: CommandRunner, adb: str, serial: str) -> None:
        self._runner = runner
        self._adb = adb
        self._serial = serial

    def foreground_package(self) -> str | None:
        """Return the package owning Android's resumed activity, when available."""
        return parse_foreground_package(self._run("shell", "dumpsys", "activity", "activities"))

    def capture_png(self) -> bytes:
        """Capture the full device display as PNG bytes."""
        try:
            result = self._runner.run(
                self._args("exec-out", "screencap", "-p"),
                capture_output=True,
                check=True,
                text=False,
            )
        except subprocess.CalledProcessError as error:
            raise _command_error(error) from error
        image = result.stdout
        if not isinstance(image, bytes) or not image.startswith(_PNG_SIGNATURE):
            raise LiveError("Android device screencap did not return a PNG image")
        return image

    def tap(self, x: float, y: float) -> None:
        """Tap screen fractions, mapped to the current full-device pixel dimensions."""
        px, py = self._point((x, y))
        self._run("shell", "input", "tap", str(px), str(py))

    def swipe(
        self,
        start: tuple[float, float],
        end: tuple[float, float],
        duration_ms: int | None = None,
    ) -> None:
        """Swipe between full-device screen fractions."""
        x1, y1 = self._point(start)
        x2, y2 = self._point(end)
        duration = duration_ms if duration_ms is not None else _DEFAULT_SWIPE_DURATION_MS
        self._run("shell", "input", "swipe", str(x1), str(y1), str(x2), str(y2), str(duration))

    def tap_text(
        self, text: str, match: TextMatch | None = None, index: int | None = None
    ) -> TextNode:
        """Tap a visible Android UI hierarchy label."""
        self._run("shell", "uiautomator", "dump", _DUMP_PATH)
        xml = self._run("exec-out", "cat", _DUMP_PATH)
        node = find_text_node(xml, text, match, index)
        self._run("shell", "input", "tap", str(node.center[0]), str(node.center[1]))
        return node

    def _point(self, point: tuple[float, float]) -> tuple[int, int]:
        width, height = parse_wm_size(self._run("shell", "wm", "size"))
        rotation = parse_display_rotation(self._run("shell", "dumpsys", "display"))
        if rotation in (1, 3):
            width, height = height, width
        x, y = point
        return int(width * x), int(height * y)

    def _run(self, *arguments: str) -> str:
        try:
            result = self._runner.run(
                self._args(*arguments),
                capture_output=True,
                check=True,
                text=True,
            )
        except subprocess.CalledProcessError as error:
            raise _command_error(error) from error
        return result.stdout

    def _args(self, *arguments: str) -> list[str]:
        return [self._adb, "-s", self._serial, *arguments]


def _command_error(error: subprocess.CalledProcessError) -> LiveError:
    """Convert adb subprocess failures to the live session's user-facing error."""
    stderr = error.stderr
    if isinstance(stderr, bytes):
        stderr = stderr.decode(errors="replace")
    detail = str(stderr).strip() or str(error)
    return LiveError(f"Android device command failed: {detail}", output=detail)
