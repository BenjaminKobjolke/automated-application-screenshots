from pathlib import Path

from screenshot_tool.config import DemoSpec
from screenshot_tool.web_browser import build_demo_url, is_app_url
from screenshot_tool.web_config import parse_web


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
