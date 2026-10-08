"""Guard batch files offered as Tickets Watcher commands."""

import re
from pathlib import Path

import pytest


TOOLS_DIR = Path(__file__).resolve().parents[2] / "tools"
BATCH_FILES = sorted(
    path
    for path in TOOLS_DIR.iterdir()
    if path.suffix.lower() in {".bat", ".cmd"} and not path.name.startswith(".")
)


@pytest.mark.parametrize("batch_file", BATCH_FILES, ids=lambda path: path.name)
def test_batch_file_finishes_without_input_and_returns_status(batch_file: Path) -> None:
    lines = batch_file.read_text(encoding="utf-8").splitlines()
    assert not any(re.match(r"^\s*pause\b", line, re.IGNORECASE) for line in lines)
    assert next(line for line in reversed(lines) if line.strip()).strip().lower().startswith(
        "exit /b"
    )
