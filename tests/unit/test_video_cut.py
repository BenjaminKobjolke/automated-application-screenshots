from pathlib import Path

import imageio_ffmpeg

from screenshot_tool.compose import ffmpeg, video


def test_cut_to_mp4_keeps_requested_duration(tmp_path: Path) -> None:
    source = tmp_path / "source.mp4"
    output = tmp_path / "cut.mp4"
    ffmpeg.run(
        [
            "-f", "lavfi", "-i", "color=c=red:s=32x32:r=10:d=2",
            "-c:v", "libx264", "-pix_fmt", "yuv420p", str(source),
        ]
    )

    video.cut_to_mp4(source, 0.5, 1.5, 10, output)

    frames = imageio_ffmpeg.read_frames(str(output))
    metadata = next(frames)
    assert 0.9 <= metadata["duration"] <= 1.1
    frames.close()
