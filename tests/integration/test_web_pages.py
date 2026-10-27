"""Integration coverage for configured web page screenshots."""

from __future__ import annotations

import json

from PIL import Image
from web_test_servers import require_edge, start_servers, stop_servers

from screenshot_tool import config
from screenshot_tool.web_pages_cli import WebPagesCLI


def test_web_pages_cli_captures_each_configured_page(tmp_path):
    require_edge()
    app, other, threads, _requests = start_servers()
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
                        "pages": [
                            {"name": "home", "path": "/home"},
                            {"name": "settings", "path": "/settings"},
                        ],
                    },
                }
            ),
            encoding="utf-8",
        )
        config.load_config(cfg)

        assert WebPagesCLI(config.settings.web).run() == 0

        output = tmp_path / "out" / "pages"
        for name in ("home", "settings"):
            with Image.open(output / f"{name}.png") as image:
                assert image.size == (320, 240)
    finally:
        stop_servers(app, other, threads)
