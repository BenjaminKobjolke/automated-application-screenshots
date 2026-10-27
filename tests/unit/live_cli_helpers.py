"""Shared input and response helpers for live CLI tests."""

import io
import json

from screenshot_tool.live_cli import LiveCLI
from screenshot_tool.live_session import LiveSession


def make_cli(lines: list[str], session: LiveSession) -> tuple[LiveCLI, io.StringIO]:
    output = io.StringIO()
    input_text = "\n".join(lines) + ("\n" if lines else "")
    return LiveCLI(session, io.StringIO(input_text), output), output


def responses(output: io.StringIO) -> list[dict[str, object]]:
    return [json.loads(line) for line in output.getvalue().splitlines()]
