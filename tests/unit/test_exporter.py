"""Unit tests for GIF/MP4 export from captured frames."""

from PIL import Image

from screenshot_tool.exporter import export_gif, export_mp4, frame_durations_ms


def make_frames(count=3, size=(16, 16)):
    colors = [(255, 0, 0), (0, 255, 0), (0, 0, 255), (255, 255, 0)]
    return [Image.new("RGB", size, colors[i % len(colors)]) for i in range(count)]


def test_frame_durations_from_timestamps():
    assert frame_durations_ms([0.0, 0.1, 0.3]) == [100, 200, 200]


def test_frame_durations_single_frame():
    assert frame_durations_ms([5.0]) == [100]


def test_frame_durations_clamped_to_minimum():
    assert frame_durations_ms([0.0, 0.001]) == [20, 20]


def test_export_gif_writes_all_frames(tmp_path):
    path = tmp_path / "demo.gif"
    export_gif(make_frames(3), [0.0, 0.1, 0.2], path)

    with Image.open(path) as gif:
        assert gif.n_frames == 3


def test_export_mp4_is_readable(tmp_path):
    import imageio.v2 as imageio

    path = tmp_path / "demo.mp4"
    export_mp4(make_frames(4), fps=10, path=path)

    assert path.stat().st_size > 0
    reader = imageio.get_reader(path)
    try:
        assert reader.count_frames() >= 4
        # macro_block_size=1 must keep the odd 16x16 size unscaled
        assert reader.get_data(0).shape[:2] == (16, 16)
    finally:
        reader.close()
