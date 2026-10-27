"""Integration coverage for browser demos and plain web page capture."""

from __future__ import annotations

import json

from PIL import Image
from web_test_servers import require_edge, start_servers, stop_servers

from screenshot_tool import config
from screenshot_tool.demo_cli import DemoCLI


def test_web_demo_records_still_video_gif_and_scopes_login_header(tmp_path):
    require_edge()
    app, other, threads, requests = start_servers()
    try:
        data = {
            "output_dir": str(tmp_path / "out"),
            "web": {
                "base_url": f"http://127.0.0.1:{app.server_port}",
                "viewport": {"width": 320, "height": 240},
                "headless": True,
                "channel": "msedge",
                "login_header": {"name": "X-Test-Login", "value": "demo-key"},
            },
            "demos": [{"id": 1, "name": "overview", "formats": ["gif", "mp4"]}],
        }
        cfg = tmp_path / "web.json"
        cfg.write_text(json.dumps(data), encoding="utf-8")
        config.load_config(cfg)

        assert DemoCLI().run("1") == 0

        output = tmp_path / "out" / "demos" / "overview"
        still = Image.open(output / "overview.png")
        assert still.size == (320, 240)
        assert (output / "demo.mp4").stat().st_size > 500
        assert (output / "demo.gif").read_bytes().startswith(b"GIF")
        assert any(path.startswith("app:") and header == "demo-key" for path, header in requests)
        assert any(path.startswith("other:") and header is None for path, header in requests)
    finally:
        stop_servers(app, other, threads)


def test_web_demo_rejects_unsafe_screenshot_names(tmp_path):
    require_edge()
    app, other, threads, _requests = start_servers("../../outside")
    try:
        cfg = tmp_path / "web.json"
        cfg.write_text(
            json.dumps(
                {
                    "output_dir": str(tmp_path / "out"),
                    "web": {
                        "base_url": f"http://127.0.0.1:{app.server_port}",
                        "viewport": {"width": 320, "height": 240},
                        "headless": True,
                        "channel": "msedge",
                    },
                    "demos": [{"id": 1, "name": "overview", "formats": ["png"]}],
                }
            ),
            encoding="utf-8",
        )
        config.load_config(cfg)

        assert DemoCLI().run("1") == 1
        assert not (tmp_path / "outside.png").exists()
        assert not list((tmp_path / "out").rglob("*.png"))
    finally:
        stop_servers(app, other, threads)
