"""Tests for uploaded stills and still-only desktop demos."""

import subprocess
from io import BytesIO
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
    recorder.request_still.assert_called_once_with("captured", None)
    recorder.save_uploaded_still.assert_called_once_with("uploaded", b"png")


def test_event_loop_passes_target_hwnd_to_recording_request():
    recorder = MagicMock(spec=Recorder)
    recorder.is_alive.return_value = True
    server = _server_with_events(
        DemoEvent("screenshot", None, "second", 77),
        DemoEvent("demo_ended", None, None, None),
    )

    assert desktop_demo._event_loop(server, _proc(), recorder)
    recorder.request_still.assert_called_once_with("second", 77)


def test_event_loop_captures_single_still_when_recorder_is_not_running():
    recorder = MagicMock(spec=Recorder)
    recorder.is_alive.return_value = False
    recorder.capture_still.return_value = False
    server = _server_with_events(DemoEvent("screenshot", None, "home", None))

    assert not desktop_demo._event_loop(server, _proc(), recorder)
    recorder.capture_still.assert_called_once_with("home", None)


def test_event_loop_passes_target_hwnd_to_one_off_capture():
    recorder = MagicMock(spec=Recorder)
    recorder.is_alive.return_value = False
    server = _server_with_events(
        DemoEvent("screenshot", None, "second", 77),
        DemoEvent("demo_ended", None, None, None),
    )

    assert desktop_demo._event_loop(server, _proc(), recorder)
    recorder.capture_still.assert_called_once_with("second", 77)


def test_capture_still_applies_crop_and_records_name(tmp_path, monkeypatch):
    recorder = Recorder(1, 10, tmp_path, crop=(1, 1, 1, 1))
    monkeypatch.setattr(WindowCapture, "capture_window", lambda _hwnd: Image.new("RGB", (10, 10)))

    assert recorder.capture_still("cropped")
    with Image.open(tmp_path / "cropped.png") as image:
        assert image.size == (8, 8)
    assert recorder.saved_stills == ["cropped"]


def test_capture_still_returns_false_when_capture_fails(tmp_path, monkeypatch):
    recorder = Recorder(1, 10, tmp_path)

    def fail_capture(_hwnd: int) -> Image.Image:
        raise RuntimeError("desktop unavailable")

    monkeypatch.setattr(WindowCapture, "capture_window", fail_capture)

    assert not recorder.capture_still("failed")
    assert recorder.saved_stills == []
    assert not (tmp_path / "failed.png").exists()


def test_uploaded_oversized_still_is_scaled(tmp_path):
    recorder = Recorder(1, 10, tmp_path, max_size=(1920, 1080))
    buffer = BytesIO()
    Image.new("RGB", (3840, 2160)).save(buffer, format="PNG")
    server = _server_with_events(
        DemoEvent("screenshot", None, "home", None, png=buffer.getvalue()),
        DemoEvent("demo_ended", None, None, None),
    )

    assert desktop_demo._event_loop(server, _proc(), recorder)
    with Image.open(tmp_path / "home.png") as image:
        assert image.size == (1920, 1080)


def test_uploaded_smaller_still_is_byte_identical(tmp_path):
    recorder = Recorder(1, 10, tmp_path, max_size=(1920, 1080))
    buffer = BytesIO()
    Image.new("RGB", (1280, 800)).save(buffer, format="PNG")
    png = buffer.getvalue()
    recorder.save_uploaded_still("home", png)

    assert (tmp_path / "home.png").read_bytes() == png


def test_undecodable_uploaded_still_is_saved_unchanged(tmp_path):
    recorder = Recorder(1, 10, tmp_path, max_size=(1920, 1080))

    recorder.save_uploaded_still("home", b"not an image")

    assert (tmp_path / "home.png").read_bytes() == b"not an image"


def test_capture_still_scales_image_after_crop(tmp_path, monkeypatch):
    recorder = Recorder(1, 10, tmp_path, max_size=(1920, 1080))
    monkeypatch.setattr(
        WindowCapture,
        "capture_window",
        lambda _hwnd: Image.new("RGB", (3840, 2160)),
    )

    assert recorder.capture_still("large")
    with Image.open(tmp_path / "large.png") as image:
        assert image.size == (1920, 1080)


def test_capture_still_uses_target_hwnd_and_defaults_to_demo_hwnd(tmp_path, monkeypatch):
    recorder = Recorder(1, 10, tmp_path)
    captured_hwnds = []

    def capture(hwnd: int) -> Image.Image:
        captured_hwnds.append(hwnd)
        size = (30, 20) if hwnd == 77 else (10, 10)
        return Image.new("RGB", size)

    monkeypatch.setattr(WindowCapture, "capture_window", capture)

    assert recorder.capture_still("second", 77)
    assert recorder.capture_still("main")

    assert captured_hwnds == [77, 1]
    with Image.open(tmp_path / "second.png") as image:
        assert image.size == (30, 20)
    with Image.open(tmp_path / "main.png") as image:
        assert image.size == (10, 10)


def test_pending_stills_capture_target_hwnd_and_keep_default_frame(tmp_path, monkeypatch):
    recorder = Recorder(1, 10, tmp_path)
    captured_hwnds = []
    recorder.request_still("main")
    recorder.request_still("second", 77)
    frame = Image.new("RGB", (10, 10))

    def capture(hwnd: int) -> Image.Image:
        captured_hwnds.append(hwnd)
        return Image.new("RGB", (30, 20))

    monkeypatch.setattr(WindowCapture, "capture_window", capture)

    recorder._save_pending_stills(frame)

    assert captured_hwnds == [77]
    with Image.open(tmp_path / "main.png") as image:
        assert image.size == (10, 10)
    with Image.open(tmp_path / "second.png") as image:
        assert image.size == (30, 20)


def test_pending_target_capture_failure_logs_and_saves_other_stills(tmp_path, monkeypatch):
    recorder = Recorder(1, 10, tmp_path)
    recorder.request_still("failed", 77)
    recorder.request_still("main")
    error = MagicMock()
    monkeypatch.setattr("screenshot_tool.recorder.AppLogger.error", error)

    def capture(hwnd: int) -> Image.Image:
        if hwnd == 77:
            raise RuntimeError("window gone")
        return Image.new("RGB", (10, 10))

    monkeypatch.setattr(WindowCapture, "capture_window", capture)

    recorder._save_pending_stills(Image.new("RGB", (10, 10)))

    assert not (tmp_path / "failed.png").exists()
    assert (tmp_path / "main.png").exists()
    error.assert_called_once_with("Still capture failed for 'failed' (hwnd 77): window gone")


def test_pending_still_is_scaled_without_changing_recorded_frame(tmp_path):
    recorder = Recorder(1, 10, tmp_path, max_size=(1920, 1080))
    recorder.request_still("next")
    frame = Image.new("RGB", (3840, 2160))

    recorder._save_pending_stills(frame)

    assert frame.size == (3840, 2160)
    with Image.open(tmp_path / "next.png") as image:
        assert image.size == (1920, 1080)


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


def test_export_scales_only_oversized_video_frames(tmp_path, monkeypatch):
    frames = [
        (0.0, Image.new("RGB", (3840, 2160))),
        (0.1, Image.new("RGB", (1280, 720))),
    ]
    recorder = MagicMock(spec=Recorder)
    recorder.frames = frames
    recorder.saved_stills = []
    monkeypatch.setattr(desktop_demo, "export_gif", MagicMock())
    monkeypatch.setattr(desktop_demo, "export_mp4", MagicMock())
    demo = DemoSpec(
        id=1,
        name="demo",
        formats=("gif", "mp4"),
        width=1920,
        height=1080,
        scale_to_window_size=True,
    )

    desktop_demo._export(demo, recorder, tmp_path)

    for exporter in (desktop_demo.export_gif, desktop_demo.export_mp4):
        images = exporter.call_args.args[0]
        assert [image.size for image in images] == [(1920, 1080), (1280, 720)]


def test_export_leaves_frames_unchanged_when_scaling_is_off(tmp_path, monkeypatch):
    recorder = MagicMock(spec=Recorder)
    recorder.frames = [(0.0, Image.new("RGB", (3840, 2160)))]
    recorder.saved_stills = []
    monkeypatch.setattr(desktop_demo, "export_gif", MagicMock())

    desktop_demo._export(DemoSpec(id=1, name="demo"), recorder, tmp_path)

    images = desktop_demo.export_gif.call_args.args[0]
    assert images[0].size == (3840, 2160)
