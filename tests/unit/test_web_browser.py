from pathlib import Path
from unittest.mock import MagicMock

from playwright.sync_api import Browser

from screenshot_tool.config import DemoSpec
from screenshot_tool.web_browser import WebBrowser, build_demo_url, is_app_url
from screenshot_tool.web_config import WebDevice, parse_web


def _web(base_url: str = "https://example.test/ax-suite"):
    return parse_web(
        Path("config.json"),
        {"base_url": base_url},
    )


def _demo(path: str = "/admin/overview") -> DemoSpec:
    return DemoSpec(id=1, name="overview", path=path)


def test_build_demo_url_includes_port_and_demo_parameters() -> None:
    assert build_demo_url(_web(), _demo(), 4321, None) == (
        "https://example.test/ax-suite/admin/overview?"
        "automation-demo=1&automation-demo-port=4321"
    )


def test_build_demo_url_preserves_existing_query_and_adds_language() -> None:
    assert build_demo_url(
        _web("https://example.test/ax-suite?tenant=alpha"),
        _demo("/admin/overview?tab=users"),
        4321,
        "de",
    ) == (
        "https://example.test/ax-suite/admin/overview?tenant=alpha&tab=users&"
        "automation-demo=1&automation-demo-port=4321&automation-demo-language=de"
    )


def test_is_app_url_matches_exact_origin_and_paths() -> None:
    assert is_app_url("https://example.test:8443", "https://example.test:8443/admin")
    assert not is_app_url("https://example.test", "https://evil-example.test/admin")
    assert not is_app_url("https://example.test", "http://example.test/admin")
    assert not is_app_url("https://example.test", "https://example.test:8443/admin")


def test_create_desktop_context_keeps_desktop_options() -> None:
    browser = WebBrowser(_web())
    browser._browser = MagicMock(spec=Browser)
    browser._playwright = MagicMock(devices={"Pixel 7": {"user_agent": "UA"}})

    browser.create_context(locale="de")

    options = browser._browser.new_context.call_args.kwargs
    assert options["viewport"] == {"width": 1280, "height": 800}
    assert options["locale"] == "de"
    assert "is_mobile" not in options
    assert "user_agent" not in options


def test_create_mobile_context_uses_phone_profile() -> None:
    browser = WebBrowser(_web())
    browser._browser = MagicMock(spec=Browser)
    browser._playwright = MagicMock(devices={"Pixel 7": {"user_agent": "UA"}})

    browser.create_context(device=WebDevice.MOBILE)

    options = browser._browser.new_context.call_args.kwargs
    assert options["viewport"] == {"width": 390, "height": 844}
    assert options["is_mobile"] is True
    assert options["has_touch"] is True
    assert options["device_scale_factor"] == 3
    assert options["user_agent"] == "UA"


def test_create_mobile_context_uses_configured_mobile_viewport() -> None:
    browser = WebBrowser(
        parse_web(
            Path("config.json"),
            {
                "base_url": "https://example.test",
                "mobile_viewport": {"width": 360, "height": 740},
            },
        )
    )
    browser._browser = MagicMock(spec=Browser)
    browser._playwright = MagicMock(devices={"Pixel 7": {"user_agent": "UA"}})

    browser.create_context(device=WebDevice.MOBILE)

    assert browser._browser.new_context.call_args.kwargs["viewport"] == {
        "width": 360,
        "height": 740,
    }
