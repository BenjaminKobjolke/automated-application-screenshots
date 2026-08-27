"""Integration test: the stills GIF encoder against the real ffmpeg.

Everything else about composition is asserted on command strings; this is the
one test that proves the bundled ffmpeg is reachable and the filter graph is
one ffmpeg will actually accept.
"""

from PIL import Image

from screenshot_tool.compose import fit, gif


def write_still(path, color):
    Image.new("RGB", (320, 200), color).save(path)
    return path


def test_stills_become_a_playable_gif(tmp_path):
    images = [
        write_still(tmp_path / "a-dark.png", (20, 20, 30)),
        write_still(tmp_path / "b-light.png", (240, 240, 230)),
    ]
    output = tmp_path / "themes.gif"

    gif.stills_to_gif(images, {"hold": 1.0, "width": 240, "colors": 64}, output)

    assert output.stat().st_size > 0
    with Image.open(output) as animation:
        assert animation.format == "GIF"
        assert animation.n_frames == 2  # one frame per still, holding the delay
        assert animation.size[0] == 240


def test_a_budget_shrinks_the_gif(tmp_path):
    # A noisy still so the palette actually costs something to encode.
    noisy = Image.new("RGB", (640, 400))
    noisy.putdata([((x * 7) % 256, (x * 13) % 256, (x * 29) % 256) for x in range(640 * 400)])
    noisy.save(tmp_path / "noise.png")
    images = [tmp_path / "noise.png"]

    unbounded = tmp_path / "big.gif"
    gif.stills_to_gif(images, {"hold": 1.0, "width": 640, "colors": 256}, unbounded)
    budget = int(unbounded.stat().st_size * 0.5)

    fitted = tmp_path / "small.gif"
    result = fit.encode_to_budget(
        lambda settings, path: gif.stills_to_gif(images, settings, path),
        {"hold": 1.0, "width": 640, "colors": 256},
        fitted,
        max_bytes=budget,
        fit=("colors", "width"),
    )
    assert fitted.is_file()
    assert result.size < unbounded.stat().st_size
