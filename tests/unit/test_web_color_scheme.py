"""Validation for the optional web color scheme setting."""

import pytest

from screenshot_tool.web_config import parse_web


@pytest.mark.parametrize("color_scheme", ["light", "dark"])
def test_web_config_parses_color_scheme(tmp_path, color_scheme):
    settings = parse_web(
        tmp_path / "app.json",
        {"base_url": "https://example.test", "color_scheme": color_scheme},
    )

    assert settings.color_scheme == color_scheme


@pytest.mark.parametrize(
    "data",
    [
        {"base_url": "https://example.test"},
        {"base_url": "https://example.test", "color_scheme": None},
    ],
)
def test_web_config_color_scheme_defaults_to_unset(tmp_path, data: dict[str, str | None]):
    settings = parse_web(tmp_path / "app.json", data)

    assert settings.color_scheme is None


@pytest.mark.parametrize("color_scheme", ["blue", 1])
def test_web_config_rejects_invalid_color_scheme(tmp_path, color_scheme):
    with pytest.raises(SystemExit, match=r"web\.color_scheme"):
        parse_web(
            tmp_path / "app.json",
            {"base_url": "https://example.test", "color_scheme": color_scheme},
        )
