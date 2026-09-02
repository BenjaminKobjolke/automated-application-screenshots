"""Integration test: NetworkDemoCLI against a fake phone app over a real socket."""

import base64
import json
import socket
import threading
from pathlib import Path

from screenshot_tool import config
from screenshot_tool.demo_cli import DemoCLI
from screenshot_tool.demo_server import DemoServer
from screenshot_tool import network_demo_cli
from screenshot_tool.network_demo_cli import NetworkDemoCLI

PNG = b"\x89PNG\r\n\x1a\nfake"
MP4 = b"\x00\x00\x00\x18ftypmp42" + b"x" * 100


def fake_app(port: int, received: list[dict]) -> threading.Thread:
    def run() -> None:
        with socket.create_connection(("127.0.0.1", port), timeout=10) as conn:
            reader = conn.makefile("rb")
            while True:
                line = reader.readline()
                if not line:
                    return
                cmd = json.loads(line)
                received.append(cmd)
                demo = cmd["demo"]
                conn.sendall(json.dumps({"event": "demo_started", "demo": demo}).encode() + b"\n")
                still = {
                    "event": "screenshot",
                    "name": "home",
                    "png": base64.b64encode(PNG).decode(),
                }
                conn.sendall(json.dumps(still).encode() + b"\n")
                conn.sendall(json.dumps({"event": "demo_ended", "demo": demo}).encode() + b"\n")
                if cmd["video"]:
                    header = {"event": "video", "demo": demo, "size": len(MP4)}
                    conn.sendall(json.dumps(header).encode() + b"\n" + MP4)

    thread = threading.Thread(target=run, daemon=True)
    thread.start()
    return thread


def test_network_run_writes_stills_video_and_gif(tmp_path, monkeypatch):
    texts_dir = tmp_path / "texts"
    texts_dir.mkdir()
    (texts_dir / "de.json").write_text('{"price": "Preis"}', encoding="utf-8")
    data = {
        "output_dir": str(tmp_path / "out"),
        "texts_dir": str(texts_dir),
        "network": {"port": 0},
        "demos": [
            {
                "id": 1,
                "name": "overview",
                "formats": ["gif", "mp4"],
                "languages": ["de"],
                "app_settings": {"api_host": "demo"},
                "pixel_ratio": 2.0,
            },
            {
                "id": 2,
                "name": "settings",
                "formats": ["png"],
                "steps": [{"type": "tap", "key": "settings_button"}],
            },
        ],
    }
    cfg = tmp_path / "app.json"
    cfg.write_text(json.dumps(data), encoding="utf-8")
    config.load_config(cfg)

    gifs: list[tuple[Path, Path]] = []
    monkeypatch.setattr(
        network_demo_cli,
        "clip_to_gif",
        lambda src, settings, out: gifs.append((src, out)) or out.write_bytes(b"GIF"),
    )

    received: list[dict] = []
    server = DemoServer("127.0.0.1", 0)
    thread = fake_app(server.port, received)
    try:
        assert NetworkDemoCLI(server).run(config.settings.demos) == 0
    finally:
        server.close()
        thread.join(timeout=5)

    out = tmp_path / "out" / "demos"
    assert (out / "overview" / "de" / "home.png").read_bytes() == PNG
    assert (out / "overview" / "de" / "demo.mp4").read_bytes() == MP4
    assert (out / "overview" / "de" / "demo.gif").exists()
    assert gifs == [(out / "overview" / "de" / "demo.mp4", out / "overview" / "de" / "demo.gif")]
    assert (out / "settings" / "home.png").read_bytes() == PNG
    assert not (out / "settings" / "demo.mp4").exists()

    start_1, start_2 = received
    assert start_1["command"] == "start" and start_1["demo"] == 1 and start_1["video"] is True
    assert start_1["language"] == "de" and start_1["texts"] == {"price": "Preis"}
    assert start_1["settings"] == {"api_host": "demo"} and start_1["pixel_ratio"] == 2.0
    assert start_2["video"] is False and start_2["steps"] == [
        {"type": "tap", "key": "settings_button"}
    ]


def test_demo_cli_dispatches_to_network_mode(tmp_path, monkeypatch):
    data = {
        "output_dir": str(tmp_path),
        "network": {"port": 0, "accept_timeout": 300},
        "demos": [{"id": 1, "name": "a"}],
    }
    cfg = tmp_path / "app.json"
    cfg.write_text(json.dumps(data), encoding="utf-8")
    config.load_config(cfg)
    seen = {}
    monkeypatch.setattr(
        NetworkDemoCLI, "run", lambda self, demos: 0 if [d.id for d in demos] == [1] else 1
    )
    monkeypatch.setattr(
        NetworkDemoCLI,
        "__init__",
        lambda self, server, accept_timeout: seen.update(accept_timeout=accept_timeout),
    )
    assert DemoCLI().run("all") == 0
    # The configured window must reach the runner, not the 30 s default.
    assert seen["accept_timeout"] == 300.0
