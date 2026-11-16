"""Validation for web target settings and demo mode parsing."""

import pytest

from screenshot_tool.web_config import (
    DEFAULT_CHANNEL,
    DEFAULT_MOBILE_VIEWPORT,
    DEFAULT_VIEWPORT,
    parse_web,
)


def test_web_config_defaults_and_derived_origin(tmp_path):
    settings = parse_web(tmp_path / "app.json", {"base_url": "https://example.test/app/"})

    assert settings.base_url == "https://example.test/app"
    assert settings.origin == "https://example.test"
    assert settings.viewport == DEFAULT_VIEWPORT
    assert settings.mobile_viewport == DEFAULT_MOBILE_VIEWPORT
    assert settings.channel == DEFAULT_CHANNEL
    assert settings.headless is True
    assert settings.ignore_https_errors is False
    assert settings.languages == ()
    assert settings.pages == ()
    assert settings.login_header is None
    assert settings.color_scheme is None


def test_web_config_parses_pages_language_and_login_header(tmp_path):
    settings = parse_web(
        tmp_path / "app.json",
        {
            "base_url": "http://example.test:8080/root",
            "login_header": {"name": "X-Login", "value": "secret-value"},
            "viewport": {"width": 1024, "height": 768},
            "mobile_viewport": {"width": 360, "height": 740},
            "languages": ["de"],
            "pages": [{"name": "overview", "path": "/admin/overview"}],
        },
    )

    assert settings.origin == "http://example.test:8080"
    assert settings.login_header is not None
    assert settings.login_header.name == "X-Login"
    assert settings.login_header.value == "secret-value"
    assert settings.languages == ("de",)
    assert settings.mobile_viewport == (360, 740)
    assert settings.pages[0].name == "overview"
    assert "secret-value" not in repr(settings)


def test_web_page_wait_until_defaults_to_networkidle(tmp_path):
    settings = parse_web(
        tmp_path / "app.json",
        {
            "base_url": "https://example.test",
            "pages": [{"name": "overview", "path": "/admin/overview"}],
        },
    )

    assert settings.pages[0].wait_until == "networkidle"


def test_web_page_wait_until_accepts_domcontentloaded(tmp_path):
    settings = parse_web(
        tmp_path / "app.json",
        {
            "base_url": "https://example.test",
            "pages": [
                {"name": "video", "path": "/video.mp4", "wait_until": "domcontentloaded"}
            ],
        },
    )

    assert settings.pages[0].wait_until == "domcontentloaded"


def test_web_page_wait_for_video_frame_defaults_to_false(tmp_path):
    settings = parse_web(
        tmp_path / "app.json",
        {"base_url": "https://example.test", "pages": [{"name": "video", "path": "/video.mp4"}]},
    )

    assert settings.pages[0].wait_for_video_frame is False


def test_web_page_wait_for_video_frame_accepts_true(tmp_path):
    settings = parse_web(
        tmp_path / "app.json",
        {
            "base_url": "https://example.test",
            "pages": [
                {
                    "name": "video",
                    "path": "/video.mp4",
                    "wait_until": "domcontentloaded",
                    "wait_for_video_frame": True,
                }
            ],
        },
    )

    assert settings.pages[0].wait_for_video_frame is True


@pytest.mark.parametrize("value", ["yes", 1])
def test_web_page_wait_for_video_frame_rejects_non_boolean(tmp_path, value):
    with pytest.raises(SystemExit) as error:
        parse_web(
            tmp_path / "app.json",
            {
                "base_url": "https://example.test",
                "pages": [{"name": "video", "path": "/video.mp4", "wait_for_video_frame": value}],
            },
        )

    assert "web.pages[0].wait_for_video_frame must be a boolean" in str(error.value)


@pytest.mark.parametrize("wait_until", ["idle", 5])
def test_web_page_wait_until_rejects_values_outside_playwright_options(tmp_path, wait_until):
    with pytest.raises(SystemExit) as error:
        parse_web(
            tmp_path / "app.json",
            {
                "base_url": "https://example.test",
                "pages": [{"name": "video", "path": "/video.mp4", "wait_until": wait_until}],
            },
        )

    message = str(error.value)
    assert "web.pages[0].wait_until" in message
    assert "commit, domcontentloaded, load, networkidle" in message


@pytest.mark.parametrize("data", [{"base_url": "ftp://example.test"}, {"base_url": "https:///missing-host"}])
def test_web_base_url_requires_http_scheme_and_host(tmp_path, data):
    with pytest.raises(SystemExit, match=r"web\.base_url"):
        parse_web(tmp_path / "app.json", data)


def test_web_config_rejects_unknown_keys(tmp_path):
    with pytest.raises(SystemExit, match=r"unknown option.*surprise"):
        parse_web(tmp_path / "app.json", {"base_url": "https://example.test", "surprise": True})


@pytest.mark.parametrize("viewport", [{"width": True, "height": 800}, {"width": 0, "height": 800}, {"width": 800, "height": -1}])
def test_web_viewport_dimensions_must_be_positive_integers(tmp_path, viewport):
    with pytest.raises(SystemExit, match=r"web\.viewport"):
        parse_web(tmp_path / "app.json", {"base_url": "https://example.test", "viewport": viewport})


@pytest.mark.parametrize(
    "viewport",
    [{"width": True, "height": 800}, {"width": 0, "height": 800}],
)
def test_web_mobile_viewport_dimensions_must_be_positive_integers(tmp_path, viewport):
    with pytest.raises(SystemExit, match=r"web\.mobile_viewport"):
        parse_web(
            tmp_path / "app.json",
            {"base_url": "https://example.test", "mobile_viewport": viewport},
        )


def test_web_pages_must_have_unique_names(tmp_path):
    with pytest.raises(SystemExit, match="unique"):
        parse_web(
            tmp_path / "app.json",
            {
                "base_url": "https://example.test",
                "pages": [{"name": "home", "path": "/"}, {"name": "home", "path": "/other"}],
            },
        )


@pytest.mark.parametrize("path", ["admin", ""])
def test_web_page_paths_must_start_with_slash(tmp_path, path):
    with pytest.raises(SystemExit, match="path"):
        parse_web(
            tmp_path / "app.json",
            {"base_url": "https://example.test", "pages": [{"name": "home", "path": path}]},
        )


@pytest.mark.parametrize("header", [{"name": "", "value": "secret"}, {"name": "X-Login", "value": ""}])
def test_web_login_header_fields_must_be_non_empty(tmp_path, header):
    with pytest.raises(SystemExit, match="login_header"):
        parse_web(tmp_path / "app.json", {"base_url": "https://example.test", "login_header": header})


