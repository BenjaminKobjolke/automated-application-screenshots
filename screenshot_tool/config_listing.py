"""Print the capabilities configured for the screenshot tool."""

from . import config
from .app_logger import AppLogger
from .cli import ScreenshotCLI


def list_config() -> None:
    """Print what the loaded config can record and build.

    The config is the only place that knows which demos exist, what they are
    grouped into and what gets built from them - reading it back is cheaper
    than reading the JSON, and it can't drift from what the tool will do.
    """
    settings = config.settings
    if settings.demos:
        AppLogger.info("Demos:")
        for demo in settings.demos:
            details = [f"{demo.width}x{demo.height}" if demo.width else "", f"{demo.fps} fps"]
            details.append("/".join(demo.formats) if demo.formats else "stills only")
            if demo.group:
                details.append(f"group: {demo.group}")
            if demo.languages:
                details.append(f"languages: {', '.join(demo.languages)}")
            AppLogger.info(
                f"  {demo.id:>3}  {demo.name:<24} {'  '.join(d for d in details if d)}"
            )
    if settings.web is not None and settings.web.pages:
        AppLogger.info("Web pages:")
        for page in settings.web.pages:
            AppLogger.info(f"  {page.name:<24} {page.path}")
    if settings.compose:
        AppLogger.info("\nCompose steps:")
        for step in settings.compose:
            source = f"group {step.group}" if step.group else f"demo {step.demo}"
            budget = f", max {step.max_size / 1000 / 1000:.1f}MB" if step.max_size else ""
            AppLogger.info(f"  {step.type:<12} {step.output:<32} from {source}{budget}")
    if settings.language_names:
        AppLogger.info("\nLanguages:")
        ScreenshotCLI().list_languages()
    if not (
        settings.demos
        or settings.compose
        or settings.language_names
        or (settings.web is not None and settings.web.pages)
    ):
        AppLogger.info("This config defines no demos, web pages, compose steps or languages.")
