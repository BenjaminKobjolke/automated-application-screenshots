"""Typed and validated settings for web screenshot targets."""

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, NoReturn
from urllib.parse import urlsplit, urlunsplit

DEFAULT_VIEWPORT = (1280, 800)
DEFAULT_CHANNEL = "msedge"


@dataclass(frozen=True)
class LoginHeader:
    """An origin-scoped login header; its value must never appear in logs."""

    name: str
    value: str = field(repr=False)


@dataclass(frozen=True)
class WebPage:
    """A named page to capture without requiring an embedded connector."""

    name: str
    path: str


@dataclass(frozen=True)
class WebSettings:
    """Browser and page settings for one web application."""

    base_url: str
    viewport: tuple[int, int] = DEFAULT_VIEWPORT
    headless: bool = True
    channel: str = DEFAULT_CHANNEL
    ignore_https_errors: bool = False
    languages: tuple[str, ...] = ()
    pages: tuple[WebPage, ...] = ()
    login_header: LoginHeader | None = None

    @property
    def origin(self) -> str:
        """Return the scheme and authority used for origin checks."""
        parsed = urlsplit(self.base_url)
        return urlunsplit((parsed.scheme, parsed.netloc, "", "", ""))


_WEB_KEYS = {
    "base_url",
    "login_header",
    "viewport",
    "headless",
    "channel",
    "ignore_https_errors",
    "languages",
    "pages",
}


def _fail(config_path: Path, message: str) -> NoReturn:
    raise SystemExit(f"ERROR: Config {config_path}: {message}")


def _object(config_path: Path, value: Any, label: str, allowed: set[str]) -> dict[str, Any]:
    if not isinstance(value, dict):
        _fail(config_path, f"{label} must be an object")
    unknown = set(value) - allowed
    if unknown:
        _fail(config_path, f"{label} has unknown option(s): {', '.join(sorted(unknown))}")
    return value


def _parse_viewport(config_path: Path, raw: Any) -> tuple[int, int]:
    viewport = _object(config_path, raw, "web.viewport", {"width", "height"})
    dimensions = (viewport.get("width", DEFAULT_VIEWPORT[0]), viewport.get("height", DEFAULT_VIEWPORT[1]))
    if any(isinstance(value, bool) or not isinstance(value, int) or value <= 0 for value in dimensions):
        _fail(config_path, "web.viewport width and height must be positive integers")
    return dimensions


def _parse_login_header(config_path: Path, raw: Any) -> LoginHeader | None:
    if raw is None:
        return None
    header = _object(config_path, raw, "web.login_header", {"name", "value"})
    name, value = header.get("name"), header.get("value")
    if not isinstance(name, str) or not name.strip():
        _fail(config_path, "web.login_header.name must be a non-empty string")
    if not isinstance(value, str) or not value.strip():
        _fail(config_path, "web.login_header.value must be a non-empty string")
    return LoginHeader(name=name, value=value)


def _parse_pages(config_path: Path, raw: Any) -> tuple[WebPage, ...]:
    if not isinstance(raw, list):
        _fail(config_path, "web.pages must be a list")
    pages: list[WebPage] = []
    names: set[str] = set()
    for index, item in enumerate(raw):
        page = _object(config_path, item, f"web.pages[{index}]", {"name", "path"})
        name, path = page.get("name"), page.get("path")
        if not isinstance(name, str) or not name.strip():
            _fail(config_path, f"web.pages[{index}].name must be a non-empty string")
        if name in names:
            _fail(config_path, "web.pages names must be unique")
        if not isinstance(path, str) or not path.startswith("/"):
            _fail(config_path, f"web.pages[{index}].path must start with '/'")
        names.add(name)
        pages.append(WebPage(name=name, path=path))
    return tuple(pages)


def parse_web(config_path: Path, data: Any) -> WebSettings:
    """Validate web settings, including nested objects and origin URL."""
    values = _object(config_path, data, "web", _WEB_KEYS)
    raw_url = values.get("base_url")
    if not isinstance(raw_url, str) or not raw_url:
        _fail(config_path, "web.base_url must be an HTTP or HTTPS URL with a host")
    parsed = urlsplit(raw_url)
    if parsed.scheme not in {"http", "https"} or not parsed.hostname:
        _fail(config_path, "web.base_url must be an HTTP or HTTPS URL with a host")
    try:
        _ = parsed.port
    except ValueError:
        _fail(config_path, "web.base_url must have a valid port")
    base_url = raw_url.rstrip("/")

    headless = values.get("headless", True)
    if not isinstance(headless, bool):
        _fail(config_path, "web.headless must be a boolean")
    ignore_https_errors = values.get("ignore_https_errors", False)
    if not isinstance(ignore_https_errors, bool):
        _fail(config_path, "web.ignore_https_errors must be a boolean")
    channel = values.get("channel", DEFAULT_CHANNEL)
    if not isinstance(channel, str) or not channel.strip():
        _fail(config_path, "web.channel must be a non-empty string")
    languages = values.get("languages", [])
    if not isinstance(languages, list) or not all(
        isinstance(language, str) and language for language in languages
    ):
        _fail(config_path, "web.languages must be a list of non-empty strings")

    return WebSettings(
        base_url=base_url,
        viewport=_parse_viewport(config_path, values.get("viewport", {})),
        headless=headless,
        channel=channel,
        ignore_https_errors=ignore_https_errors,
        languages=tuple(languages),
        pages=_parse_pages(config_path, values.get("pages", [])),
        login_header=_parse_login_header(config_path, values.get("login_header")),
    )
