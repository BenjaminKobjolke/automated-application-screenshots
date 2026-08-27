"""Unit tests for the size-budget search, against a fake encoder.

The search is arithmetic over a callback, so none of this runs ffmpeg. The
fake encoder models a GIF closely enough to be worth arguing with: size grows
with the pixel area, the frame rate and the palette depth.
"""

import pytest

from screenshot_tool.compose import fit

MB = 1000 * 1000


class FakeEncoder:
    """Writes a file whose size follows the settings it was given."""

    def __init__(self, base=8 * MB):
        self.base = base
        self.calls = []

    def size_for(self, settings):
        width = float(settings.get("width", 800))
        fps = float(settings.get("fps", 10))
        colors = float(settings.get("colors", 256))
        return int(
            self.base
            * (width / 800) ** 2
            * (fps / 10)
            * (fit.size_factor("colors", 256, colors))
        )

    def __call__(self, settings, path):
        self.calls.append(dict(settings))
        path.write_bytes(b"x" * max(1, self.size_for(settings)))


def test_under_budget_encodes_once(tmp_path):
    encoder = FakeEncoder(base=MB)
    out = tmp_path / "small.gif"
    result = fit.encode_to_budget(
        encoder,
        {"width": 800, "fps": 10, "colors": 256},
        out,
        max_bytes=2 * MB,
        fit=("colors", "fps"),
    )
    assert len(encoder.calls) == 1
    assert result.size <= 2 * MB
    assert out.is_file()


def test_no_budget_encodes_once_and_keeps_it(tmp_path):
    encoder = FakeEncoder(base=50 * MB)
    out = tmp_path / "big.gif"
    fit.encode_to_budget(encoder, {"width": 800}, out, max_bytes=None)
    assert len(encoder.calls) == 1
    assert out.stat().st_size == 50 * MB


def test_over_budget_degrades_until_it_fits(tmp_path):
    encoder = FakeEncoder(base=8 * MB)
    out = tmp_path / "gif.gif"
    result = fit.encode_to_budget(
        encoder,
        {"width": 800, "fps": 10, "colors": 256},
        out,
        max_bytes=2 * MB,
        fit=("colors", "fps", "width"),
    )
    assert result.size <= 2 * MB
    assert 1 < len(encoder.calls) <= fit.MAX_ATTEMPTS
    assert out.stat().st_size == result.size


def test_a_constraint_is_never_moved(tmp_path):
    encoder = FakeEncoder(base=20 * MB)
    out = tmp_path / "gif.gif"
    fit.encode_to_budget(
        encoder,
        {"width": 800, "fps": 10, "colors": 256},
        out,
        max_bytes=MB,
        fit=("colors", "fps"),  # width is a constraint
    )
    assert {call["width"] for call in encoder.calls} == {800}


def test_attempts_are_capped_and_never_repeated(tmp_path):
    # Nothing this encoder can be told will fit. A wild overshoot takes every
    # knob to the bottom of its ladder in one step, and once there is nothing
    # left to trade the search stops rather than re-encoding the same settings.
    encoder = FakeEncoder(base=500 * MB)
    out = tmp_path / "gif.gif"
    fit.encode_to_budget(
        encoder,
        {"width": 800, "fps": 10, "colors": 256},
        out,
        max_bytes=1000,
        fit=("colors", "fps", "width"),
    )
    assert 1 < len(encoder.calls) <= fit.MAX_ATTEMPTS
    seen = [tuple(sorted(call.items())) for call in encoder.calls]
    assert len(set(seen)) == len(seen)
    assert encoder.calls[-1] == {"width": fit.MIN_WIDTH, "fps": 3, "colors": 16}


def test_best_is_the_largest_attempt_that_fits(tmp_path):
    encoder = FakeEncoder(base=8 * MB)
    out = tmp_path / "gif.gif"
    result = fit.encode_to_budget(
        encoder,
        {"width": 800, "fps": 10, "colors": 256},
        out,
        max_bytes=2 * MB,
        fit=("colors", "fps", "width"),
    )
    fitting = [encoder.size_for(c) for c in encoder.calls if encoder.size_for(c) <= 2 * MB]
    assert result.size == max(fitting)


def test_when_nothing_fits_the_smallest_is_kept(tmp_path):
    encoder = FakeEncoder(base=500 * MB)
    out = tmp_path / "gif.gif"
    result = fit.encode_to_budget(
        encoder,
        {"width": 800, "fps": 10, "colors": 256},
        out,
        max_bytes=1000,
        fit=("colors", "fps", "width"),
    )
    assert result.size == min(encoder.size_for(c) for c in encoder.calls)
    assert out.stat().st_size == result.size


def test_missing_the_budget_warns_but_keeps_the_file(tmp_path, caplog):
    encoder = FakeEncoder(base=500 * MB)
    out = tmp_path / "gif.gif"
    fit.encode_to_budget(
        encoder, {"width": 800}, out, max_bytes=1000, fit=("width",), on_miss="warn"
    )
    assert out.is_file()
    assert "over the" in caplog.text


def test_missing_the_budget_can_be_fatal(tmp_path):
    encoder = FakeEncoder(base=500 * MB)
    with pytest.raises(RuntimeError, match="over the"):
        fit.encode_to_budget(
            encoder,
            {"width": 800},
            tmp_path / "gif.gif",
            max_bytes=1000,
            fit=("width",),
            on_miss="error",
        )


def test_empty_fit_encodes_once_and_warns(tmp_path, caplog):
    encoder = FakeEncoder(base=8 * MB)
    fit.encode_to_budget(
        encoder, {"width": 800}, tmp_path / "gif.gif", max_bytes=MB, fit=()
    )
    assert len(encoder.calls) == 1
    assert "over the" in caplog.text


# --- the ladders and the model -------------------------------------------------


def test_ladder_starts_below_the_configured_value():
    assert fit.ladder_for("colors", 64) == (48, 32, 24, 16)
    assert fit.ladder_for("fps", 5) == (4, 3)


def test_crf_ladder_goes_up_because_higher_is_smaller():
    assert fit.ladder_for("crf", 23) == (26, 28, 30, 32, 34)


def test_width_ladder_is_generated_and_floors():
    ladder = fit.ladder_for("width", 800)
    assert ladder[0] == 640
    assert ladder[-1] == fit.MIN_WIDTH
    assert all(b < a for a, b in zip(ladder, ladder[1:]))


def test_a_knob_at_the_bottom_has_no_ladder_left():
    assert fit.ladder_for("colors", 16) == ()
    assert fit.ladder_for("width", fit.MIN_WIDTH) == ()


@pytest.mark.parametrize(
    "knob,old,new,expected",
    [
        ("width", 800, 400, 0.25),  # area
        ("fps", 10, 5, 0.5),  # one frame each
        ("crf", 20, 26, 0.5),  # +6 crf halves the bitrate
    ],
)
def test_size_model(knob, old, new, expected):
    assert fit.size_factor(knob, old, new) == pytest.approx(expected)


def test_colours_shrink_sub_linearly():
    # Quartering the palette must not predict a quarter of the file.
    assert 0.5 < fit.size_factor("colors", 256, 64) < 1.0


def test_format_size():
    assert fit.format_size(2_400_000) == "2.40MB"
    assert fit.format_size(500_000) == "500KB"
