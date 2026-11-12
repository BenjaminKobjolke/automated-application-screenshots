"""Unit tests for the compose section, groups, captions and size budgets."""

import pytest
from compose_config_data import BASE, load, with_compose

from screenshot_tool import config
from screenshot_tool.config_models import Subtitle

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


def with_subtitles(subtitles):
    demos = [{**d, "subtitles": subtitles} if d["id"] == 3 else d for d in BASE["demos"]]
    return {**BASE, "demos": demos}


def test_subtitles_are_read(tmp_path):
    subtitles = [{"at": 18.5, "text": "Type to filter"}, {"at": 24, "text": "Sort", "seconds": 3}]
    settings = load(tmp_path, with_subtitles(subtitles))
    tour_a, tour_b = settings.demos_in_group("tour")
    assert tour_a.subtitles == (
        Subtitle(at=18.5, text="Type to filter"),
        Subtitle(at=24.0, text="Sort", seconds=3.0),
    )
    assert tour_b.subtitles == ()


@pytest.mark.parametrize(
    "subtitles",
    [
        {"at": 1, "text": "not a list"},
        ["not an object"],
        [{"text": "no time"}],
        [{"at": -1, "text": "before the start"}],
        [{"at": True, "text": "a typo, not 1 s"}],
        [{"at": 1}],
        [{"at": 1, "text": ""}],
        [{"at": 1, "text": "x", "seconds": 0}],
        [{"at": 1, "text": "x", "seconds": True}],
    ],
)
def test_malformed_subtitles_are_rejected(tmp_path, subtitles):
    with pytest.raises(SystemExit, match=r"tour-a.*subtitle"):
        load(tmp_path, with_subtitles(subtitles))


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


def test_config_without_compose_still_loads(tmp_path):
    assert load(tmp_path, BASE).compose == ()
