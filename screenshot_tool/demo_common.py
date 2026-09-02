"""Pieces both demo runners share: timeouts, run expansion, texts, verify.

Launch mode (``demo_cli``) records a desktop window; network mode
(``network_demo_cli``) receives what a phone recorded. Everything that does not
depend on where the pixels come from lives here.
"""

import json
from collections.abc import Callable
from pathlib import Path

from . import config
from .app_logger import AppLogger
# ACCEPT_TIMEOUT_S is defined in config (NetworkSettings defaults to it) and
# imported here so both demo runners keep reading their timeouts from one place.
from .config import ACCEPT_TIMEOUT_S, DemoSpec

EVENT_TIMEOUT_S = 60.0
DEMO_CAP_S = 300.0

RunDemo = Callable[[DemoSpec, "str | None"], bool]


def _run_label(demo: DemoSpec, language: str | None) -> str:
    """Display name of one run: 'basic-math [de]', or just the name."""
    return f"{demo.name} [{language}]" if language else demo.name


def output_dir_for(demo: DemoSpec, language: str | None) -> Path:
    """``<output_dir>/demos/<name>[/<lang>]`` - what ``compose`` reads later."""
    out_dir = Path(config.settings.output_dir) / "demos" / demo.name
    return out_dir / language if language else out_dir


def texts_file_for(demo: DemoSpec, language: str | None) -> Path | None:
    """The ``<texts_dir>/<lang>.json`` of a language run, or None.

    Raises:
        FileNotFoundError: The config names a texts_dir but the file is missing.
    """
    if not language or not config.settings.texts_dir:
        return None
    # Absolute: a launched app may run with a different cwd (launch.cwd)
    texts_file = (Path(config.settings.texts_dir) / f"{language}.json").resolve()
    if not texts_file.is_file():
        raise FileNotFoundError(
            f"Texts file missing for '{_run_label(demo, language)}': {texts_file}"
        )
    return texts_file


def load_texts(demo: DemoSpec, language: str | None) -> dict[str, str]:
    """The placeholder -> localized string map of a language run (empty if none)."""
    texts_file = texts_file_for(demo, language)
    if texts_file is None:
        return {}
    return {str(k): str(v) for k, v in json.loads(texts_file.read_text(encoding="utf-8")).items()}


def _clear_stale_stills(out_dir: Path) -> None:
    """Drop stills from a previous take of this demo.

    A still is named after what it shows (a theme, a state). If that thing is
    gone, its PNG would otherwise linger and end up in the next slideshow -
    silently, because nothing else knows it should not be there.
    """
    for stale in out_dir.glob("*.png"):
        stale.unlink()


def _run_verify(demo: DemoSpec, language: str | None) -> bool:
    """Check the demo's side effects; False (and a reason) if one is missing."""
    ok = True
    for check in demo.verify:
        path = Path(config.expand(check.path, demo, language))
        if not path.is_file():
            AppLogger.error(f"Verify failed: {check.describe()} - no such file")
            ok = False
        elif check.kind == "contains":
            content = path.read_text(encoding="utf-8", errors="replace")
            if check.text is not None and check.text not in content:
                AppLogger.error(f"Verify failed: {check.describe()}")
                ok = False
    if demo.verify and ok:
        AppLogger.info(f"Verified {len(demo.verify)} side effect(s).")
    return ok


def run_all(demos: tuple[DemoSpec, ...], run_demo: RunDemo) -> int:
    """Run every (demo, language) pair through ``run_demo`` and report.

    Returns:
        Exit code (0 when every run succeeded).
    """
    # A demo without languages is one run; with languages, one run per language
    runs = [(demo, lang) for demo in demos for lang in (demo.languages or (None,))]
    failed = [_run_label(demo, lang) for demo, lang in runs if not run_demo(demo, lang)]
    AppLogger.info(f"\n{'=' * 50}")
    AppLogger.info(f"Demos complete: {len(runs) - len(failed)}/{len(runs)} succeeded")
    for name in failed:
        AppLogger.info(f"  FAILED: {name}")
    return 0 if not failed else 1
