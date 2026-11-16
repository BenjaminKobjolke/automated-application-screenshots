"""Integration coverage for waiting on video frames during page capture."""

from __future__ import annotations

import json

from PIL import Image
from web_test_servers import require_edge, serve_directory, start_servers, stop_server, stop_servers

from screenshot_tool import config
from screenshot_tool.web_pages_cli import WebPagesCLI


def test_web_pages_cli_waits_for_decoded_video_frame(tmp_path):
    require_edge()
    media_dir = tmp_path / "media"
    media_dir.mkdir()
    video_path = media_dir / "clip.mp4"
    from screenshot_tool.compose.ffmpeg import run as run_ffmpeg

    run_ffmpeg(
        [
            "-f", "lavfi", "-i", "color=c=black:s=160x120:d=2:r=10",
            "-f", "lavfi", "-i", "color=c=red:s=160x120:d=6:r=10",
            "-f", "lavfi", "-i", "color=c=blue:s=160x120:d=6:r=10",
            "-filter_complex", "[0:v][1:v][2:v]concat=n=3:v=1:a=0[v]",
            "-map", "[v]",
            "-c:v", "libx264", "-pix_fmt", "yuv420p", "-movflags", "+faststart",
            str(video_path),
        ]
    )
    server, thread = serve_directory(media_dir)
    try:
        cfg = tmp_path / "web.json"
        cfg.write_text(
            json.dumps(
                {
                    "output_dir": str(tmp_path / "out"),
                    "web": {
                        "base_url": f"http://127.0.0.1:{server.server_port}",
                        "viewport": {"width": 320, "height": 240},
                        "headless": True,
                        "pages": [
                            {
                                "name": name,
                                "path": f"/clip.mp4#t={timestamp}",
                                "wait_until": "domcontentloaded",
                                "wait_for_video_frame": True,
                            }
                            for name, timestamp in (("early", 3), ("middle", 10))
                        ],
                    },
                }
            ),
            encoding="utf-8",
        )
        config.load_config(cfg)

        assert WebPagesCLI(config.settings.web).run() == 0

        for name, expected in (("early", "red"), ("middle", "blue")):
            with Image.open(tmp_path / "out" / "pages" / f"{name}.png") as image:
                red, green, blue = image.getpixel((image.width // 2, image.height // 2))[:3]
                if expected == "red":
                    assert red > 100 and red > green * 2 and red > blue * 2
                else:
                    assert blue > 100 and blue > red * 2 and blue > green * 2
    finally:
        stop_server(server, thread)


def test_web_pages_cli_fails_page_without_video_frame(tmp_path, monkeypatch):
    require_edge()
    app, other, threads, _requests = start_servers()
    monkeypatch.setattr("screenshot_tool.web_video_frame.VIDEO_FRAME_TIMEOUT_MS", 1000)
    try:
        cfg = tmp_path / "web.json"
        cfg.write_text(
            json.dumps(
                {
                    "output_dir": str(tmp_path / "out"),
                    "web": {
                        "base_url": f"http://127.0.0.1:{app.server_port}",
                        "headless": True,
                        "pages": [
                            {
                                "name": "plain",
                                "path": "/home",
                                "wait_for_video_frame": True,
                            }
                        ],
                    },
                }
            ),
            encoding="utf-8",
        )
        config.load_config(cfg)

        assert WebPagesCLI(config.settings.web).run() == 1
        assert not (tmp_path / "out" / "pages" / "plain.png").exists()
    finally:
        stop_servers(app, other, threads)
