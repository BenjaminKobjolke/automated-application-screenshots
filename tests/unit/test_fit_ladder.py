"""Tests for compose fit ladders and size predictions."""

import pytest

from screenshot_tool.compose import fit_ladder


def test_ladder_starts_below_the_configured_value():
    assert fit_ladder.ladder_for("colors", 64) == (48, 32, 24, 16)
    assert fit_ladder.ladder_for("fps", 5) == (4, 3)


def test_crf_ladder_goes_up_because_higher_is_smaller():
    assert fit_ladder.ladder_for("crf", 23) == (26, 28, 30, 32, 34)


def test_width_ladder_is_generated_and_floors():
    ladder = fit_ladder.ladder_for("width", 800)
    assert ladder[0] == 640
    assert ladder[-1] == fit_ladder.MIN_WIDTH
    assert all(b < a for a, b in zip(ladder, ladder[1:]))


def test_a_knob_at_the_bottom_has_no_ladder_left():
    assert fit_ladder.ladder_for("colors", 16) == ()
    assert fit_ladder.ladder_for("width", fit_ladder.MIN_WIDTH) == ()


@pytest.mark.parametrize(
    "knob,old,new,expected",
    [
        ("width", 800, 400, 0.25),  # area
        ("fps", 10, 5, 0.5),  # one frame each
        ("crf", 20, 26, 0.5),  # +6 crf halves the bitrate
    ],
)
def test_size_model(knob, old, new, expected):
    assert fit_ladder.size_factor(knob, old, new) == pytest.approx(expected)


def test_colours_shrink_sub_linearly():
    # Quartering the palette must not predict a quarter of the file.
    assert 0.5 < fit_ladder.size_factor("colors", 256, 64) < 1.0
