"""Integration coverage for browser demos and plain web page capture."""

from __future__ import annotations

import json
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import parse_qs, urlsplit

import pytest
from PIL import Image
from playwright.sync_api import Error as PlaywrightError

from screenshot_tool import config
from screenshot_tool.demo_cli import DemoCLI
from screenshot_tool.web_browser import WebBrowser
from screenshot_tool.web_pages_cli import WebPagesCLI


class _Server(ThreadingHTTPServer):
    daemon_threads = True
    allow_reuse_address = True


def _servers(screenshot_name: str = "overview"):
    requests: list[tuple[str, str | None]] = []
    app_port: list[int] = []
    other_port: list[int] = []

    class AppHandler(BaseHTTPRequestHandler):
        def do_GET(self):
            requests.append((f"app:{self.path}", self.headers.get("X-Test-Login")))
            if self.path.startswith("/record-other-origin"):
                self.send_response(200)
                self.send_header("Access-Control-Allow-Origin", f"http://127.0.0.1:{app_port[0]}")
                self.end_headers()
                self.wfile.write(b"ok")
                return
            path = urlsplit(self.path).path
            params = parse_qs(urlsplit(self.path).query)
            script = ""
            if "automation-demo" in params:
                script = f"""
                const params = new URLSearchParams(window.location.search);
                fetch('http://127.0.0.1:{other_port[0]}/other-origin').catch(() => {{}});
                const ws = new WebSocket('ws://127.0.0.1:' + params.get('automation-demo-port'));
                ws.onmessage = (message) => {{
                  const command = JSON.parse(message.data);
                  if (command.command === 'start') {{
                    ws.send(JSON.stringify({{event:'demo_started', demo: command.demo}}));
                    ws.send(JSON.stringify({{event:'screenshot', name:{json.dumps(screenshot_name)}}}));
                  }} else if (command.command === 'screenshot_done') {{
                    document.body.style.background = '#2255aa';
                    setTimeout(() => ws.send(JSON.stringify({{event:'demo_ended', demo: 1}})), 250);
                  }}
                }};
                """
            body = f"<html><body style='margin:0;background:#aa2211'><h1>{path}</h1><script>{script}</script></body></html>".encode()
            self.send_response(200)
            self.send_header("Content-Type", "text/html")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)

        def log_message(self, *_args):
            pass

    class OtherHandler(BaseHTTPRequestHandler):
        def do_GET(self):
            requests.append((f"other:{self.path}", self.headers.get("X-Test-Login")))
            self.send_response(200)
            self.end_headers()
            self.wfile.write(b"ok")

        def log_message(self, *_args):
            pass

    app = _Server(("127.0.0.1", 0), AppHandler)
    other = _Server(("127.0.0.1", 0), OtherHandler)
    app_port.append(app.server_port)
    other_port.append(other.server_port)
    threads = [threading.Thread(target=server.serve_forever, daemon=True) for server in (app, other)]
    for thread in threads:
        thread.start()
    return app, other, threads, requests


def _require_edge():
    from screenshot_tool.web_config import WebSettings

    try:
        with WebBrowser(WebSettings("http://127.0.0.1")):
            pass
    except PlaywrightError as error:
        pytest.skip(f"Microsoft Edge is unavailable: {error}")


def test_web_demo_records_still_video_gif_and_scopes_login_header(tmp_path):
    _require_edge()
    app, other, threads, requests = _servers()
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
        for server in (app, other):
            server.shutdown()
            server.server_close()
        for thread in threads:
            thread.join(timeout=3)


def test_web_demo_rejects_unsafe_screenshot_names(tmp_path):
    _require_edge()
    app, other, threads, _requests = _servers("../../outside")
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
        for server in (app, other):
            server.shutdown()
            server.server_close()
        for thread in threads:
            thread.join(timeout=3)


def test_web_pages_cli_captures_each_configured_page(tmp_path):
    _require_edge()
    app, other, threads, _requests = _servers()
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
        for server in (app, other):
            server.shutdown()
            server.server_close()
        for thread in threads:
            thread.join(timeout=3)
