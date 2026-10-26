"""Capture configured web pages as viewport screenshots."""

from __future__ import annotations

from pathlib import Path
from urllib.parse import urlsplit, urlunsplit

from playwright.sync_api import Error as PlaywrightError

from . import config
from .app_logger import AppLogger
from .demo_common import _clear_stale_stills
from .web_browser import WebBrowser
from .web_config import WebSettings


class WebPagesCLI:
    """Capture every configured page for each configured browser locale."""

    def __init__(self, web: WebSettings, output_dir: Path | None = None) -> None:
        self._web = web
        self._output_dir = output_dir

    def run(self, start_from: str | None = None) -> int:
        """Capture pages and return nonzero when any navigation fails."""
        if not self._web.pages:
            AppLogger.error("Web config has no pages to capture.")
            return 1
        output_root = (self._output_dir or Path(config.settings.output_dir)) / "pages"
        languages: tuple[str | None, ...] = self._web.languages or (None,)
        if start_from is not None and self._web.languages:
            try:
                start_index = self._web.languages.index(start_from)
            except ValueError:
                AppLogger.error(f"Unknown start language '{start_from}'.")
                return 1
            languages = self._web.languages[start_index:]
        total = len(self._web.pages) * len(languages)
        failed = 0
        AppLogger.info(f"Capturing {total} web page(s)...")
        try:
            with WebBrowser(self._web) as browser:
                for language in languages:
                    output_dir = output_root / language if language else output_root
                    output_dir.mkdir(parents=True, exist_ok=True)
                    _clear_stale_stills(output_dir)
                    context = browser.create_context(locale=language)
                    try:
                        page = context.new_page()
                        for target in self._web.pages:
                            requested = _page_url(self._web.base_url, target.path)
                            try:
                                response = page.goto(requested, wait_until="networkidle")
                                if response is not None and response.status >= 400:
                                    AppLogger.warning(
                                        f"Page '{target.name}' returned HTTP {response.status}."
                                    )
                                if urlsplit(page.url).path != urlsplit(requested).path:
                                    AppLogger.warning(
                                        f"Page '{target.name}' redirected to {page.url}."
                                    )
                                still = output_dir / f"{target.name}.png"
                                page.screenshot(path=str(still))
                                AppLogger.info(f"  {still}")
                            except PlaywrightError as error:
                                AppLogger.error(f"Unable to capture page '{target.name}': {error}")
                                failed += 1
                    finally:
                        context.close()
        except (PlaywrightError, OSError) as error:
            AppLogger.error(f"Unable to capture web pages: {error}")
            return 1
        AppLogger.info(f"Web pages complete: {total - failed}/{total} succeeded")
        return 0 if failed == 0 else 1


def _page_url(base_url: str, path: str) -> str:
    """Join an application-relative path while retaining the base subfolder."""
    base = urlsplit(base_url)
    combined_path = f"{base.path.rstrip('/')}/{path.lstrip('/')}"
    return urlunsplit((base.scheme, base.netloc, combined_path, base.query, ""))
