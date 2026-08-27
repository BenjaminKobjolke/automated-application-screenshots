"""The shipped example config must stay loadable.

config/example-full.json exercises every key there is, and CONFIG.md is its
annotation (JSON has no comments). Loading it here is what stops it drifting
away from the schema it is supposed to document.
"""

from pathlib import Path

from screenshot_tool import config

EXAMPLE = Path(__file__).resolve().parents[2] / "config" / "example-full.json"


def test_the_example_config_loads():
    settings = config.load_config(EXAMPLE)
    assert settings.launch is not None
    assert settings.demos
    assert settings.compose


def test_the_example_uses_every_documented_section():
    settings = config.load_config(EXAMPLE)
    assert settings.language_names, "language mode"
    assert settings.texts_dir, "localized demo texts"
    assert settings.launch and settings.launch.env, "child environment"
    assert any(d.group for d in settings.demos), "compose groups"
    assert any(d.caption or d.captions for d in settings.demos), "tour captions"
    assert any(d.verify for d in settings.demos), "verify checks"
    assert any(d.languages for d in settings.demos), "per-language demos"
    assert any(d.app_settings for d in settings.demos), "app settings"
    assert any(d.crop != (0, 0, 0, 0) for d in settings.demos), "crop"
    assert {s.type for s in settings.compose} == {"tour", "stills_gif", "mp4_gif"}
    assert any(s.max_size for s in settings.compose), "size budgets"
    assert any(s.fit is not None for s in settings.compose), "fit knobs"


def test_every_compose_type_is_covered():
    # A new step type without an example is a type nobody will discover.
    settings = config.load_config(EXAMPLE)
    assert set(config._COMPOSE_TYPES) == {s.type for s in settings.compose}
