"""Unit tests for the GIF encoders' ffmpeg invocations.

These assert the commands, not the pixels - the filter graphs carry the
hard-won details (palette generation, the one-frame-per-still trick, the
repeated concat entry) and a silent change to any of them is a regression the
eye would catch only in a README months later.
"""

from pathlib import Path

import pytest

from screenshot_tool.compose import ffmpeg, gif


@pytest.fixture
def runs(monkeypatch):
    """Capture ffmpeg calls instead of running them."""
    calls = []

    def fake_run(args, cwd=None):
        calls.append(args)
        # The caller stats the output, so leave something behind.
        Path(args[-1]).write_bytes(b"gif")

    monkeypatch.setattr(ffmpeg, "run", fake_run)
    return calls


def graph_of(args):
    for flag in ("-filter_complex", "-lavfi", "-vf"):
        if flag in args:
            return args[args.index(flag) + 1]
    raise AssertionError(f"no filter in {args}")


def stills(tmp_path, count=3):
    paths = []
    for i in range(count):
        path = tmp_path / f"Theme {i}.png"
        path.write_bytes(b"png")
        paths.append(path)
    return paths


# --- stills -> gif -------------------------------------------------------------


def test_stills_gif_holds_each_still_for_one_frame(tmp_path, runs):
    gif.stills_to_gif(stills(tmp_path), {"hold": 2.0, "width": 960, "colors": 256}, tmp_path / "o.gif")
    graph = graph_of(runs[0])
    assert "fps=0.5" in graph  # 1 / hold: one frame carries the whole delay
    assert "scale=960:-2:flags=lanczos" in graph
    assert "palettegen=stats_mode=diff:max_colors=256" in graph
    assert "paletteuse" in graph


def test_stills_gif_trims_the_repeated_last_entry(tmp_path, runs):
    gif.stills_to_gif(stills(tmp_path, 3), {"hold": 2.0}, tmp_path / "o.gif")
    args = runs[0]
    assert args[args.index("-t") + 1] == "6.0"  # 3 stills x 2 s, not 4 holds
    assert args[args.index("-loop") + 1] == "0"


def test_stills_gif_uses_a_concat_list_with_forward_slashes(tmp_path, monkeypatch):
    written = {}

    def fake_run(args, cwd=None):
        written["list"] = Path(args[args.index("-i") + 1]).read_text(encoding="utf-8")
        Path(args[-1]).write_bytes(b"gif")

    monkeypatch.setattr(ffmpeg, "run", fake_run)
    images = stills(tmp_path, 2)
    gif.stills_to_gif(images, {"hold": 1.5}, tmp_path / "o.gif")

    lines = written["list"].strip().splitlines()
    assert "\\" not in written["list"]
    assert lines[0] == f"file '{images[0].as_posix()}'"
    assert lines[1] == "duration 1.5"
    # The demuxer ignores the final duration, so the last entry is repeated.
    assert lines[-1] == f"file '{images[-1].as_posix()}'"


def test_stills_gif_defaults(tmp_path, runs):
    gif.stills_to_gif(stills(tmp_path), {}, tmp_path / "o.gif")
    graph = graph_of(runs[0])
    assert "scale=960:-2" in graph
    assert "max_colors=256" in graph


# --- mp4 -> gif ----------------------------------------------------------------


def test_clip_gif_is_two_pass(tmp_path, runs):
    gif.clip_to_gif(tmp_path / "demo.mp4", {"fps": 5, "width": 800, "colors": 64}, tmp_path / "o.gif")
    assert len(runs) == 2
    assert runs[0][-1].endswith("palette.png")
    assert "palettegen=max_colors=64" in graph_of(runs[0])


def test_clip_gif_uses_bayer_dithering(tmp_path, runs):
    gif.clip_to_gif(tmp_path / "demo.mp4", {}, tmp_path / "o.gif")
    assert "paletteuse=dither=bayer:bayer_scale=5" in graph_of(runs[1])


def test_clip_gif_scales_and_drops_frames_in_both_passes(tmp_path, runs):
    gif.clip_to_gif(tmp_path / "demo.mp4", {"fps": 8, "width": 640}, tmp_path / "o.gif")
    for args in runs:
        assert "fps=8,scale=640:-1:flags=lanczos" in graph_of(args)


def test_clip_gif_defaults(tmp_path, runs):
    gif.clip_to_gif(tmp_path / "demo.mp4", {}, tmp_path / "o.gif")
    assert "fps=5,scale=800:-1" in graph_of(runs[0])
    assert "max_colors=64" in graph_of(runs[0])
