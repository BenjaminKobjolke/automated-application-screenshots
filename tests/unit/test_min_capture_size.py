"""Tests for opt-in minimum dimensions on saved desktop captures."""

import json
from io import BytesIO
from unittest.mock import MagicMock

import pytest
from demo_config_data import DEMO_ONLY, write_config
from PIL import Image

from screenshot_tool import config, desktop_demo
from screenshot_tool.capture import WindowCapture
from screenshot_tool.config import DemoSpec
from screenshot_tool.image_fit import size_shortfall
from screenshot_tool.recorder import Recorder

MINIMUM = {"width": 1280, "height": 768}


def _copy_demo_config():
    return json.loads(json.dumps(DEMO_ONLY))


def test_top_level_minimum_applies_with_per_demo_override_and_null(tmp_path):
    data = _copy_demo_config()
    data["min_capture_size"] = MINIMUM
    data["demos"][0]["min_capture_size"] = {"width": 1600, "height": 900}
    data["demos"][1]["min_capture_size"] = None

    settings = config.load_config(write_config(tmp_path, data))

    assert settings.demos[0].min_capture_size == (1600, 900)
    assert settings.demos[1].min_capture_size is None


def test_top_level_minimum_applies_to_each_demo(tmp_path):
    data = _copy_demo_config()
    data["min_capture_size"] = MINIMUM

    settings = config.load_config(write_config(tmp_path, data))

    assert [demo.min_capture_size for demo in settings.demos] == [(1280, 768)] * 2


def test_minimum_defaults_to_none(tmp_path):
    settings = config.load_config(write_config(tmp_path, DEMO_ONLY))

    assert all(demo.min_capture_size is None for demo in settings.demos)


@pytest.mark.parametrize(
    "bad",
    [
        [],
        {"width": 1280},
        {"height": 768},
        {"width": 0, "height": 768},
        {"width": 1280, "height": -1},
        {"width": True, "height": 768},
        {"width": 1280, "height": False},
        {"width": 1280.0, "height": 768},
        {"width": "1280", "height": 768},
    ],
)
def test_invalid_minimum_is_rejected(tmp_path, bad):
    data = _copy_demo_config()
    data["demos"][0]["min_capture_size"] = bad

    with pytest.raises(SystemExit, match="min_capture_size"):
        config.load_config(write_config(tmp_path, data))


@pytest.mark.parametrize("location", ["top-level", "per-demo"])
def test_minimum_must_be_an_object_or_null(tmp_path, location):
    data = _copy_demo_config()
    if location == "top-level":
        data["min_capture_size"] = "1280x768"
    else:
        data["demos"][0]["min_capture_size"] = "1280x768"

    with pytest.raises(SystemExit, match="min_capture_size"):
        config.load_config(write_config(tmp_path, data))


@pytest.mark.parametrize("mode", ["network", "web"])
def test_minimum_is_rejected_for_non_launch_modes(tmp_path, mode):
    data = _copy_demo_config()
    del data["launch"]
    data[mode] = {"port": 5000} if mode == "network" else {}
    data["demos"][0]["min_capture_size"] = MINIMUM

    with pytest.raises(SystemExit, match="min_capture_size"):
        config.load_config(write_config(tmp_path, data))


def test_minimum_cannot_exceed_scaled_output_size(tmp_path):
    data = _copy_demo_config()
    data["demos"][0]["scale_to_window_size"] = True
    data["demos"][0]["min_capture_size"] = MINIMUM

    with pytest.raises(SystemExit, match="min_capture_size"):
        config.load_config(write_config(tmp_path, data))


@pytest.mark.parametrize(
    ("actual", "minimum", "is_shortfall"),
    [
        ((1280, 768), (1280, 768), False),
        ((1920, 1080), (1280, 768), False),
        ((1024, 768), (1280, 768), True),
        ((1280, 600), (1280, 768), True),
        ((1024, 600), (1280, 768), True),
    ],
)
def test_size_shortfall_checks_both_dimensions(actual, minimum, is_shortfall):
    result = size_shortfall("still 'home'", actual, minimum)

    if is_shortfall:
        assert result is not None
        assert "1024x600" in result or f"{actual[0]}x{actual[1]}" in result
        assert "1280x768" in result
    else:
        assert result is None


def test_capture_still_keeps_undersized_image_and_reports_failure(tmp_path, monkeypatch):
    recorder = Recorder(1, 10, tmp_path, min_size=(1280, 768))
    monkeypatch.setattr(
        WindowCapture,
        "capture_window",
        lambda _hwnd: Image.new("RGB", (1024, 600)),
    )

    assert not recorder.capture_still("home")
    assert (tmp_path / "home.png").exists()
    assert len(recorder.size_errors) == 1
    assert "home" in recorder.size_errors[0]


def test_capture_still_at_minimum_passes(tmp_path, monkeypatch):
    recorder = Recorder(1, 10, tmp_path, min_size=(1280, 768))
    monkeypatch.setattr(
        WindowCapture,
        "capture_window",
        lambda _hwnd: Image.new("RGB", (1280, 768)),
    )

    assert recorder.capture_still("home")
    assert recorder.size_errors == []


def test_capture_still_without_minimum_remains_opt_in(tmp_path, monkeypatch):
    recorder = Recorder(1, 10, tmp_path)
    monkeypatch.setattr(
        WindowCapture,
        "capture_window",
        lambda _hwnd: Image.new("RGB", (16, 12)),
    )

    assert recorder.capture_still("tiny")
    assert recorder.size_errors == []


def test_capture_checks_dimensions_after_crop_and_fit(tmp_path, monkeypatch):
    recorder = Recorder(1, 10, tmp_path, crop=(0, 30, 0, 0), min_size=(1280, 768))
    monkeypatch.setattr(
        WindowCapture,
        "capture_window",
        lambda _hwnd: Image.new("RGB", (1300, 800)),
    )

    assert not recorder.capture_still("cropped")
    with Image.open(tmp_path / "cropped.png") as image:
        assert image.size == (1270, 800)


def test_uploaded_still_records_undersized_png(tmp_path):
    recorder = Recorder(1, 10, tmp_path, min_size=(1280, 768))
    buffer = BytesIO()
    Image.new("RGB", (1024, 600)).save(buffer, format="PNG")

    recorder.save_uploaded_still("uploaded", buffer.getvalue())

    assert (tmp_path / "uploaded.png").exists()
    assert len(recorder.size_errors) == 1
    assert "uploaded" in recorder.size_errors[0]


def test_invalid_uploaded_bytes_are_saved_and_report_unverifiable_size(tmp_path):
    recorder = Recorder(1, 10, tmp_path, min_size=(1280, 768))

    recorder.save_uploaded_still("invalid", b"not a PNG")

    assert (tmp_path / "invalid.png").read_bytes() == b"not a PNG"
    assert len(recorder.size_errors) == 1
    assert "invalid" in recorder.size_errors[0]


def test_pending_still_records_size_shortfall(tmp_path):
    recorder = Recorder(1, 10, tmp_path, min_size=(1280, 768))
    recorder.request_still("pending")

    recorder._save_pending_stills(Image.new("RGB", (1024, 600)))

    assert (tmp_path / "pending.png").exists()
    assert len(recorder.size_errors) == 1


def test_export_checks_fitted_video_frames_and_still_runs(tmp_path, monkeypatch):
    recorder = MagicMock(spec=Recorder)
    recorder.frames = [(0.0, Image.new("RGB", (1024, 600)))]
    recorder.saved_stills = []
    monkeypatch.setattr(desktop_demo, "export_gif", MagicMock())
    demo = DemoSpec(id=1, name="demo", formats=("gif",), min_capture_size=(1280, 768))

    assert not desktop_demo._export(demo, recorder, tmp_path)
    desktop_demo.export_gif.assert_called_once()


def test_export_passes_at_minimum_and_without_minimum(tmp_path, monkeypatch):
    recorder = MagicMock(spec=Recorder)
    recorder.frames = [(0.0, Image.new("RGB", (1280, 768)))]
    recorder.saved_stills = []
    monkeypatch.setattr(desktop_demo, "export_gif", MagicMock())
    demo = DemoSpec(id=1, name="demo", formats=("gif",), min_capture_size=(1280, 768))

    assert desktop_demo._export(demo, recorder, tmp_path)

    no_minimum = DemoSpec(id=1, name="demo", formats=("gif",))
    assert desktop_demo._export(no_minimum, recorder, tmp_path)
