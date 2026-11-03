"""Integration coverage for configured web page screenshots."""

from __future__ import annotations

import json

from PIL import Image
from web_test_servers import require_edge, start_servers, stop_servers

from screenshot_tool import config
from screenshot_tool.web_config import WebDevice
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


def test_web_pages_cli_writes_mobile_screenshots_separately(tmp_path):
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
                        "mobile_viewport": {"width": 320, "height": 240},
                        "headless": True,
                        "languages": ["de"],
                        "pages": [{"name": "home", "path": "/home"}],
                    },
                }
            ),
            encoding="utf-8",
        )
        config.load_config(cfg)

        web = config.settings.web
        assert WebPagesCLI(web).run() == 0
        assert WebPagesCLI(web, device=WebDevice.MOBILE).run() == 0

        output = tmp_path / "out" / "pages"
        with Image.open(output / "de" / "home.png") as image:
            assert image.size == (320, 240)
        with Image.open(output / "mobile" / "de" / "home.png") as image:
            assert image.size == (960, 720)
    finally:
        stop_servers(app, other, threads)
