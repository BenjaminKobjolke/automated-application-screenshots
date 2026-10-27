"""Shared local web servers for browser integration tests."""

from __future__ import annotations

import json
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from typing import TypeAlias
from urllib.parse import parse_qs, urlsplit

import pytest
from playwright.sync_api import Error as PlaywrightError

from screenshot_tool.web_browser import WebBrowser

RequestLog: TypeAlias = list[tuple[str, str | None]]


class _Server(ThreadingHTTPServer):
    daemon_threads = True
    allow_reuse_address = True


def start_servers(
    screenshot_name: str = "overview",
) -> tuple[_Server, _Server, list[threading.Thread], RequestLog]:
    """Start app and secondary-origin servers used by web integration tests."""
    requests: RequestLog = []
    app_port: list[int] = []
    other_port: list[int] = []

    class AppHandler(BaseHTTPRequestHandler):
        def do_GET(self):
            requests.append((f"app:{self.path}", self.headers.get("X-Test-Login")))
            if self.path.startswith("/record-other-origin"):
                self.send_response(200)
                self.send_header(
                    "Access-Control-Allow-Origin", f"http://127.0.0.1:{app_port[0]}"
                )
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
            body = (
                f"<html><body style='margin:0;background:#aa2211'><h1>{path}</h1>"
                f"<script>{script}</script></body></html>"
            ).encode()
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


def stop_servers(app: _Server, other: _Server, threads: list[threading.Thread]) -> None:
    """Stop both local servers and join their serving threads."""
    for server in (app, other):
        server.shutdown()
        server.server_close()
    for thread in threads:
        thread.join(timeout=3)


def require_edge() -> None:
    """Skip browser integration tests when Microsoft Edge is unavailable."""
    from screenshot_tool.web_config import WebSettings

    try:
        with WebBrowser(WebSettings("http://127.0.0.1")):
            pass
    except PlaywrightError as error:
        pytest.skip(f"Microsoft Edge is unavailable: {error}")
