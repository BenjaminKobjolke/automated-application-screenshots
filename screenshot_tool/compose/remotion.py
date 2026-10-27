"""Locate Remotion and render compositions with its command line."""

from __future__ import annotations

import json
import shutil
import subprocess
import tempfile
from pathlib import Path
from typing import Any

from .. import config
from ..app_logger import AppLogger

COMPOSER_DIR = Path(__file__).resolve().parents[2] / "composer"
COMPOSITION_ID = "Tour"


def npx() -> str:
    """The npx executable, or a readable explanation of its absence."""
    found = shutil.which("npx")
    if not found:
        raise RuntimeError(
            "The 'tour' compose step renders with Remotion, which needs Node.js "
            "(18 or newer) on PATH - 'npx' was not found. Install Node, then run "
            "'npm install' in " + str(COMPOSER_DIR) + ". Recording and the GIF "
            "steps do not need Node."
        )
    return found


def ensure_installed() -> None:
    if not (COMPOSER_DIR / "node_modules").is_dir():
        raise RuntimeError(
            f"Remotion is not installed yet - run 'npm install' in {COMPOSER_DIR}"
        )


def render(props: dict[str, Any], crf: int, destination: Path) -> None:
    """Run the Remotion render, streaming its output into the tool's log."""
    with tempfile.TemporaryDirectory() as work:
        props_file = Path(work) / "props.json"
        props_file.write_text(json.dumps(props), encoding="utf-8")
        command = [
            npx(), "remotion", "render", "src/index.ts", COMPOSITION_ID, str(destination),
            f"--props={props_file}",
            # The recordings folder is the public dir, so clips are loaded in place.
            f"--public-dir={Path(config.settings.output_dir)}",
            "--codec=h264",
            f"--crf={crf}",
            "--log=info",
        ]
        AppLogger.info(f"Rendering {len(props['clips'])} chapters with Remotion...")
        result = subprocess.run(command, cwd=str(COMPOSER_DIR), shell=False)
    if result.returncode:
        raise RuntimeError(f"Remotion render failed ({result.returncode})")
