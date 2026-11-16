"""Typed models and defaults for web screenshot settings."""

from dataclasses import dataclass, field
from enum import Enum
from typing import Literal
from urllib.parse import urlsplit, urlunsplit

DEFAULT_VIEWPORT = (1280, 800)
DEFAULT_MOBILE_VIEWPORT = (390, 844)
DEFAULT_CHANNEL = "msedge"
PageWaitUntil = Literal["commit", "domcontentloaded", "load", "networkidle"]
ColorScheme = Literal["light", "dark"]
DEFAULT_PAGE_WAIT_UNTIL: PageWaitUntil = "networkidle"


class WebDevice(Enum):
    """Device profile used to capture configured web pages."""

    DESKTOP = "desktop"
    MOBILE = "mobile"


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
    wait_until: PageWaitUntil = DEFAULT_PAGE_WAIT_UNTIL
    wait_for_video_frame: bool = False


@dataclass(frozen=True)
class WebSettings:
    """Browser and page settings for one web application."""

    base_url: str
    viewport: tuple[int, int] = DEFAULT_VIEWPORT
    mobile_viewport: tuple[int, int] = DEFAULT_MOBILE_VIEWPORT
    headless: bool = True
    channel: str = DEFAULT_CHANNEL
    ignore_https_errors: bool = False
    languages: tuple[str, ...] = ()
    pages: tuple[WebPage, ...] = ()
    login_header: LoginHeader | None = None
    color_scheme: ColorScheme | None = None

    @property
    def origin(self) -> str:
        """Return the scheme and authority used for origin checks."""
        parsed = urlsplit(self.base_url)
        return urlunsplit((parsed.scheme, parsed.netloc, "", "", ""))
