"""Validation for web target settings and demo mode parsing."""

import json
from pathlib import Path

import pytest

from screenshot_tool.config import load_config
from screenshot_tool.web_config import DEFAULT_CHANNEL, DEFAULT_VIEWPORT, parse_web


def write_config(tmp_path: Path, data: dict) -> Path:
    path = tmp_path / "app.json"
    path.write_text(json.dumps(data), encoding="utf-8")
    return path


def test_web_config_defaults_and_derived_origin(tmp_path):
    settings = parse_web(tmp_path / "app.json", {"base_url": "https://example.test/app/"})

    assert settings.base_url == "https://example.test/app"
    assert settings.origin == "https://example.test"
    assert settings.viewport == DEFAULT_VIEWPORT
    assert settings.channel == DEFAULT_CHANNEL
    assert settings.headless is True
    assert settings.ignore_https_errors is False
    assert settings.languages == ()
    assert settings.pages == ()
    assert settings.login_header is None


def test_web_config_parses_pages_language_and_login_header(tmp_path):
    settings = parse_web(
        tmp_path / "app.json",
        {
            "base_url": "http://example.test:8080/root",
            "login_header": {"name": "X-Login", "value": "secret-value"},
            "viewport": {"width": 1024, "height": 768},
            "languages": ["de"],
            "pages": [{"name": "overview", "path": "/admin/overview"}],
        },
    )

    assert settings.origin == "http://example.test:8080"
    assert settings.login_header is not None
    assert settings.login_header.name == "X-Login"
    assert settings.login_header.value == "secret-value"
    assert settings.languages == ("de",)
    assert settings.pages[0].name == "overview"
    assert "secret-value" not in repr(settings)


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


def test_web_only_config_loads_pages_without_demos(tmp_path):
    settings = load_config(
        write_config(
            tmp_path,
            {
                "output_dir": "shots",
                "web": {
                    "base_url": "https://example.test",
                    "pages": [{"name": "home", "path": "/"}],
                },
            },
        )
    )

    assert settings.web is not None
    assert settings.web.pages[0].name == "home"
    assert settings.demos == ()
    assert settings.launch is None
    assert settings.network is None


def test_web_mode_conflicts_with_launch_mode(tmp_path):
    with pytest.raises(SystemExit, match="exactly one"):
        load_config(
            write_config(
                tmp_path,
                {
                    "output_dir": "shots",
                    "process_name": "app.exe",
                    "title_substring": "App",
                    "web": {"base_url": "https://example.test"},
                    "launch": {"command": ["app.exe"]},
                    "demos": [{"id": 1, "name": "home"}],
                },
            )
        )


def test_web_demo_path_defaults_to_root(tmp_path):
    settings = load_config(
        write_config(
            tmp_path,
            {
                "output_dir": "shots",
                "web": {"base_url": "https://example.test"},
                "demos": [{"id": 1, "name": "home"}],
            },
        )
    )

    assert settings.demos[0].path == "/"


def test_web_demo_path_must_start_with_slash(tmp_path):
    with pytest.raises(SystemExit, match="path"):
        load_config(
            write_config(
                tmp_path,
                {
                    "output_dir": "shots",
                    "web": {"base_url": "https://example.test"},
                    "demos": [{"id": 1, "name": "home", "path": "admin"}],
                },
            )
        )


def test_web_demo_dimensions_must_be_paired(tmp_path):
    with pytest.raises(SystemExit, match=r"width.*height|height.*width"):
        load_config(
            write_config(
                tmp_path,
                {
                    "output_dir": "shots",
                    "web": {"base_url": "https://example.test"},
                    "demos": [{"id": 1, "name": "home", "width": 900}],
                },
            )
        )
