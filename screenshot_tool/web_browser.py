"""Playwright browser lifecycle and URL helpers for web screenshot targets."""

from __future__ import annotations

from pathlib import Path
from typing import Any
from urllib.parse import parse_qsl, urlencode, urlsplit, urlunsplit

from playwright.sync_api import Browser, BrowserContext, Error, Playwright, Route, sync_playwright

from .app_logger import AppLogger
from .config import DemoSpec
from .web_config import WebSettings

_AUTOMATION_PARAMETERS = {
    "automation-demo",
    "automation-demo-port",
    "automation-demo-language",
}


def build_demo_url(
    web: WebSettings, demo: DemoSpec, port: int, language: str | None
) -> str:
    """Build the connector URL while preserving base and page query parameters."""
    base = urlsplit(web.base_url)
    demo_path = urlsplit(demo.path)
    path = f"{base.path.rstrip('/')}/{demo_path.path.lstrip('/')}"
    query = [
        (key, value)
        for key, value in (*parse_qsl(base.query, keep_blank_values=True), *parse_qsl(demo_path.query, keep_blank_values=True))
        if key not in _AUTOMATION_PARAMETERS
    ]
    query.extend(
        [
            ("automation-demo", str(demo.id)),
            ("automation-demo-port", str(port)),
        ]
    )
    if language is not None:
        query.append(("automation-demo-language", language))
    return urlunsplit((base.scheme, base.netloc, path, urlencode(query), demo_path.fragment or base.fragment))


def is_app_url(origin: str, url: str) -> bool:
    """Return whether ``url`` uses the exact scheme and authority of ``origin``."""
    expected = urlsplit(origin)
    candidate = urlsplit(url)
    return (
        candidate.scheme.lower() == expected.scheme.lower()
        and candidate.netloc.lower() == expected.netloc.lower()
        and bool(candidate.hostname)
    )


class WebBrowser:
    """Own Playwright and its browser; each demo can create an isolated context."""

    def __init__(self, web: WebSettings) -> None:
        self._web = web
        self._playwright_context: Any = None
        self._playwright: Playwright | None = None
        self._browser: Browser | None = None

    def __enter__(self) -> WebBrowser:
        self._playwright_context = sync_playwright()
        self._playwright = self._playwright_context.start()
        try:
            self._browser = self._playwright.chromium.launch(
                channel=self._web.channel,
                headless=self._web.headless,
            )
        except Error as error:
            AppLogger.error(
                f"Unable to launch browser channel '{self._web.channel}'. "
                "Install Microsoft Edge, or set channel to 'chromium' and run "
                "'playwright install chromium'. "
                f"Browser error: {error}"
            )
            self._playwright.stop()
            self._playwright = None
            self._playwright_context = None
            raise
        return self

    def create_context(
        self,
        viewport: tuple[int, int] | None = None,
        locale: str | None = None,
        record_video_dir: Path | None = None,
    ) -> BrowserContext:
        """Create a context with configured viewport and origin-scoped login."""
        if self._browser is None:
            raise RuntimeError("WebBrowser must be entered before creating a context")
        options: dict[str, Any] = {
            "viewport": {
                "width": (viewport or self._web.viewport)[0],
                "height": (viewport or self._web.viewport)[1],
            },
            "ignore_https_errors": self._web.ignore_https_errors,
        }
        if locale:
            options["locale"] = locale
        if record_video_dir is not None:
            options["record_video_dir"] = str(record_video_dir)
            options["record_video_size"] = {
                "width": (viewport or self._web.viewport)[0],
                "height": (viewport or self._web.viewport)[1],
            }
        context = self._browser.new_context(**options)
        if self._web.login_header is not None:
            header = self._web.login_header

            def add_login_header(route: Route) -> None:
                if is_app_url(self._web.origin, route.request.url):
                    headers = dict(route.request.headers)
                    headers[header.name] = header.value
                    route.continue_(headers=headers)
                else:
                    route.continue_()

            context.route("**/*", add_login_header)
        return context

    def close(self) -> None:
        """Close browser resources, including on exceptional runs."""
        if self._browser is not None:
            self._browser.close()
            self._browser = None
        if self._playwright_context is not None:
            if self._playwright is not None:
                self._playwright.stop()
                self._playwright = None
            self._playwright_context = None

    def __exit__(self, *_: object) -> None:
        self.close()
