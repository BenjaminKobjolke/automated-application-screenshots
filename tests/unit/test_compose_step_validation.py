"""Rejected compose-step configuration cases."""

import pytest
from compose_config_data import BASE, load, with_compose


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


def test_compose_without_demos_is_rejected(tmp_path):
    data = {k: v for k, v in BASE.items() if k not in ("demos", "launch")}
    data["compose"] = [{"type": "stills_gif", "demo": "themes", "output": "x.gif"}]
    with pytest.raises(SystemExit, match="needs a 'demos' section"):
        load(tmp_path, data)


