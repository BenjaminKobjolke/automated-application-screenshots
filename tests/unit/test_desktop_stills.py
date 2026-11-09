"""Tests for uploaded stills and still-only desktop demos."""

import subprocess
from unittest.mock import MagicMock

from PIL import Image

from screenshot_tool import desktop_demo
from screenshot_tool.capture import WindowCapture
from screenshot_tool.config import DemoSpec
from screenshot_tool.demo_protocol import DemoEvent
from screenshot_tool.demo_server import DemoServer
from screenshot_tool.recorder import Recorder


def _server_with_events(*events: DemoEvent) -> MagicMock:
    server = MagicMock(spec=DemoServer)
    server.next_event.side_effect = [*events]
    return server


def _proc() -> MagicMock:
    proc = MagicMock(spec=subprocess.Popen)
    proc.poll.return_value = None
    return proc


def test_event_loop_saves_uploaded_png_without_starting_recorder(tmp_path):
    recorder = Recorder(1, 10, tmp_path)
    server = _server_with_events(
        DemoEvent("screenshot", None, "home", None, png=b"png-bytes"),
        DemoEvent("demo_ended", None, None, None),
    )

    assert desktop_demo._event_loop(server, _proc(), recorder)
    assert (tmp_path / "home.png").read_bytes() == b"png-bytes"
    assert recorder.saved_stills == ["home"]


def test_event_loop_uses_request_for_recording_and_upload_for_png():
    recorder = MagicMock(spec=Recorder)
    recorder.is_alive.return_value = True
    server = _server_with_events(
        DemoEvent("screenshot", None, "captured", None),
        DemoEvent("screenshot", None, "uploaded", None, png=b"png"),
        DemoEvent("demo_ended", None, None, None),
    )

    assert desktop_demo._event_loop(server, _proc(), recorder)
    recorder.request_still.assert_called_once_with("captured")
    recorder.save_uploaded_still.assert_called_once_with("uploaded", b"png")


def test_event_loop_captures_single_still_when_recorder_is_not_running():
    recorder = MagicMock(spec=Recorder)
    recorder.is_alive.return_value = False
    recorder.capture_still.return_value = False
    server = _server_with_events(DemoEvent("screenshot", None, "home", None))

    assert not desktop_demo._event_loop(server, _proc(), recorder)
    recorder.capture_still.assert_called_once_with("home")


def test_capture_still_applies_crop_and_records_name(tmp_path, monkeypatch):
    recorder = Recorder(1, 10, tmp_path, crop=(1, 1, 1, 1))
    monkeypatch.setattr(WindowCapture, "capture_window", lambda hwnd: Image.new("RGB", (10, 10)))

    assert recorder.capture_still("cropped")
    with Image.open(tmp_path / "cropped.png") as image:
        assert image.size == (8, 8)
    assert recorder.saved_stills == ["cropped"]


def test_capture_still_returns_false_when_capture_fails(tmp_path, monkeypatch):
    recorder = Recorder(1, 10, tmp_path)

    def fail_capture(hwnd: int) -> Image.Image:
        raise RuntimeError("desktop unavailable")

    monkeypatch.setattr(WindowCapture, "capture_window", fail_capture)

    assert not recorder.capture_still("failed")
    assert recorder.saved_stills == []
    assert not (tmp_path / "failed.png").exists()


def test_export_allows_stills_only_demo_without_frames(tmp_path, monkeypatch):
    recorder = MagicMock(spec=Recorder)
    recorder.frames = []
    recorder.saved_stills = ["home"]
    error = MagicMock()
    monkeypatch.setattr(desktop_demo.AppLogger, "error", error)
    monkeypatch.setattr(desktop_demo, "export_gif", MagicMock())
    monkeypatch.setattr(desktop_demo, "export_mp4", MagicMock())

    desktop_demo._export(DemoSpec(id=1, name="demo", formats=()), recorder, tmp_path)

    error.assert_not_called()
    desktop_demo.export_gif.assert_not_called()
    desktop_demo.export_mp4.assert_not_called()
