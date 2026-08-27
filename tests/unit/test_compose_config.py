"""Unit tests for the compose section, groups, captions and size budgets."""

import json

import pytest

from screenshot_tool import config

BASE = {
    "process_name": "python.exe",
    "title_substring": "fman",
    "output_dir": "media",
    "launch": {"command": ["run.bat", "{demo_id}", "{port}"]},
    "demos": [
        {"id": 1, "name": "themes", "formats": []},
        {"id": 3, "name": "tour-a", "group": "tour", "caption": "Two panes"},
        {"id": 4, "name": "tour-b", "group": "tour", "captions": {"de": "Zwei"}},
        {"id": 8, "name": "feature-goto", "group": "feature"},
    ],
}


def with_compose(*steps):
    return {**BASE, "compose": list(steps)}


def write_config(tmp_path, data):
    path = tmp_path / "app.json"
    path.write_text(json.dumps(data), encoding="utf-8")
    return path


def load(tmp_path, data):
    return config.load_config(write_config(tmp_path, data))


# --- sizes --------------------------------------------------------------------


@pytest.mark.parametrize(
    "text,expected",
    [
        ("2MB", 2_000_000),
        ("1.5MB", 1_500_000),
        ("500KB", 500_000),
        ("500 kb", 500_000),
        ("1024B", 1024),
        ("1500000", 1_500_000),
        (2048, 2048),
    ],
)
def test_parse_size(text, expected):
    assert config.parse_size(text) == expected


def test_parse_size_rejects_nonsense():
    with pytest.raises(ValueError):
        config.parse_size("big")


# --- demo fields --------------------------------------------------------------


def test_group_and_caption_are_read(tmp_path):
    settings = load(tmp_path, BASE)
    tour = settings.demos_in_group("tour")
    assert [d.name for d in tour] == ["tour-a", "tour-b"]
    assert tour[0].caption == "Two panes"


def test_demos_in_group_is_id_ordered(tmp_path):
    data = {**BASE, "demos": list(reversed(BASE["demos"]))}
    settings = load(tmp_path, data)
    assert [d.id for d in settings.demos_in_group("tour")] == [3, 4]


def test_caption_for_language_falls_back(tmp_path):
    settings = load(tmp_path, BASE)
    tour_a, tour_b = settings.demos_in_group("tour")
    assert tour_a.caption_for("de") == "Two panes"  # no German wording, use the default
    assert tour_b.caption_for("de") == "Zwei"
    assert tour_b.caption_for(None) is None


def test_relative_output_dir_resolves_against_the_config(tmp_path):
    settings = load(tmp_path, BASE)
    assert settings.output_dir == str(tmp_path / "media")


def test_absolute_output_dir_is_left_alone(tmp_path):
    settings = load(tmp_path, {**BASE, "output_dir": "D:/elsewhere/media"})
    assert settings.output_dir.replace("\\", "/").lower() == "d:/elsewhere/media"


# --- compose steps ------------------------------------------------------------


def test_compose_step_parses(tmp_path):
    settings = load(
        tmp_path,
        with_compose(
            {
                "type": "mp4_gif",
                "group": "feature",
                "output": "features/{name}.gif",
                "fps": 5,
                "width": 800,
                "colors": 64,
                "max_size": "2MB",
                "fit": ["colors", "fps"],
            }
        ),
    )
    step = settings.compose[0]
    assert step.type == "mp4_gif"
    assert step.group == "feature"
    assert step.settings == {"fps": 5, "width": 800, "colors": 64}
    assert step.max_size == 2_000_000
    assert step.fit_knobs == ("colors", "fps")
    assert step.on_miss == "warn"


def test_fit_defaults_per_type(tmp_path):
    settings = load(
        tmp_path,
        with_compose({"type": "stills_gif", "demo": "themes", "output": "themes.gif"}),
    )
    # lossy first: it costs neither resolution nor frames, so it is the
    # cheapest thing to spend before touching either.
    assert settings.compose[0].fit_knobs == ("lossy", "colors", "width")


def test_unknown_type_is_rejected(tmp_path):
    with pytest.raises(SystemExit, match="expected one of"):
        load(tmp_path, with_compose({"type": "webm", "demo": "themes", "output": "x.webm"}))


def test_step_needs_exactly_one_source(tmp_path):
    with pytest.raises(SystemExit, match="exactly one of"):
        load(tmp_path, with_compose({"type": "stills_gif", "output": "themes.gif"}))
    with pytest.raises(SystemExit, match="exactly one of"):
        load(
            tmp_path,
            with_compose(
                {
                    "type": "stills_gif",
                    "demo": "themes",
                    "group": "tour",
                    "output": "themes.gif",
                }
            ),
        )


def test_group_with_no_demos_is_rejected(tmp_path):
    with pytest.raises(SystemExit, match="names group 'nope'"):
        load(tmp_path, with_compose({"type": "mp4_gif", "group": "nope", "output": "x.gif"}))


def test_demo_that_does_not_exist_is_rejected(tmp_path):
    with pytest.raises(SystemExit, match="names demo 'nope'"):
        load(tmp_path, with_compose({"type": "stills_gif", "demo": "nope", "output": "x.gif"}))


def test_tour_chapter_without_a_caption_is_rejected(tmp_path):
    data = with_compose({"type": "tour", "group": "feature", "output": "tour.mp4"})
    with pytest.raises(SystemExit, match="no caption: feature-goto"):
        load(tmp_path, data)


def test_option_the_type_does_not_use_is_rejected(tmp_path):
    with pytest.raises(SystemExit, match="does not use"):
        load(
            tmp_path,
            with_compose(
                {"type": "stills_gif", "demo": "themes", "output": "x.gif", "crf": 26}
            ),
        )


def test_fit_knob_the_type_cannot_trade_is_rejected(tmp_path):
    with pytest.raises(SystemExit, match="cannot fit crf"):
        load(
            tmp_path,
            with_compose(
                {
                    "type": "stills_gif",
                    "demo": "themes",
                    "output": "x.gif",
                    "max_size": "1MB",
                    "fit": ["crf"],
                }
            ),
        )


def test_fit_without_a_budget_is_rejected(tmp_path):
    with pytest.raises(SystemExit, match="no 'max_size'"):
        load(
            tmp_path,
            with_compose(
                {"type": "stills_gif", "demo": "themes", "output": "x.gif", "fit": ["colors"]}
            ),
        )


def test_unreadable_max_size_is_rejected(tmp_path):
    with pytest.raises(SystemExit, match="unreadable max_size"):
        load(
            tmp_path,
            with_compose(
                {"type": "stills_gif", "demo": "themes", "output": "x.gif", "max_size": "huge"}
            ),
        )


def test_empty_fit_means_check_only(tmp_path):
    settings = load(
        tmp_path,
        with_compose(
            {
                "type": "stills_gif",
                "demo": "themes",
                "output": "x.gif",
                "max_size": "1MB",
                "fit": [],
            }
        ),
    )
    assert settings.compose[0].fit_knobs == ()


def test_compose_without_demos_is_rejected(tmp_path):
    data = {k: v for k, v in BASE.items() if k not in ("demos", "launch")}
    data["compose"] = [{"type": "stills_gif", "demo": "themes", "output": "x.gif"}]
    with pytest.raises(SystemExit, match="needs a 'demos' section"):
        load(tmp_path, data)


def test_config_without_compose_still_loads(tmp_path):
    assert load(tmp_path, BASE).compose == ()
