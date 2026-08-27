"""Unit tests for the props the tour hands to Remotion, and the transcode.

No Node and no ffmpeg here: what matters is that the chapter order, the frame
maths, the captions and the clip paths are right before a render costs
minutes.
"""

import json

import pytest

from screenshot_tool import config
from screenshot_tool.compose import ffmpeg, tour, video

CONFIG = {
    "process_name": "python.exe",
    "title_substring": "fman",
    "output_dir": "media",
    "launch": {"command": ["run.bat", "{demo_id}"]},
    "demos": [
        {
            "id": 4,
            "name": "tour-b",
            "group": "tour",
            "caption": "Organize",
            "width": 1280,
            "height": 800,
            "formats": ["mp4"],
        },
        {
            "id": 3,
            "name": "tour-a",
            "group": "tour",
            "caption": "Two panes",
            "captions": {"de": "Zwei Fenster"},
            "width": 1280,
            "height": 800,
            "formats": ["mp4"],
        },
    ],
    "compose": [
        {
            "type": "tour",
            "group": "tour",
            "output": "tour/feature-tour.mp4",
            "width": 1280,
            "fps": 30,
            "caption_seconds": 4,
            "intro": {"title": "fman", "subtitle": "keyboard-first"},
        }
    ],
}


@pytest.fixture
def loaded(tmp_path, monkeypatch):
    """A loaded config whose chapter clips exist on disk."""
    path = tmp_path / "app.json"
    path.write_text(json.dumps(CONFIG), encoding="utf-8")
    settings = config.load_config(path)
    for name in ("tour-a", "tour-b"):
        # Language-less and per-language takes both, so a German tour has
        # German clips to join.
        for folder in (tmp_path / "media" / "demos" / name, ) + (
            tmp_path / "media" / "demos" / name / "de",
        ):
            folder.mkdir(parents=True, exist_ok=True)
            (folder / "demo.mp4").write_bytes(b"mp4")
    monkeypatch.setattr(tour, "_clip_seconds", lambda path: 6.5)
    return settings


def props_of(settings, language=None):
    step = settings.compose[0]
    return tour._props(step, settings.demos_in_group("tour"), language)


def test_chapters_are_in_id_order_not_config_order(loaded):
    props = props_of(loaded)
    assert [c["src"] for c in props["clips"]] == [
        "demos/tour-a/demo.mp4",
        "demos/tour-b/demo.mp4",
    ]


def test_clip_paths_are_relative_and_forward_slashed(loaded):
    # They become URLs under Remotion's public dir; a Windows path is not one.
    for clip in props_of(loaded)["clips"]:
        assert "\\" not in clip["src"]
        assert not clip["src"].startswith("/")


def test_durations_are_frames_at_the_composition_fps(loaded):
    props = props_of(loaded)
    assert all(c["durationInFrames"] == round(6.5 * 30) for c in props["clips"])


def test_total_frames_include_the_intro_card(loaded):
    props = props_of(loaded)
    clips = sum(c["durationInFrames"] for c in props["clips"])
    assert props["totalFrames"] == clips + props["intro"]["durationInFrames"]
    assert props["outro"] is None


def test_caption_seconds_become_frames(loaded):
    assert props_of(loaded)["captionFrames"] == 120  # 4 s at 30 fps


def test_captions_follow_the_language(loaded):
    assert props_of(loaded)["clips"][0]["caption"] == "Two panes"
    assert props_of(loaded, "de")["clips"][0]["caption"] == "Zwei Fenster"
    # tour-b has no German wording, so it keeps its default caption.
    assert props_of(loaded, "de")["clips"][1]["caption"] == "Organize"


def test_height_keeps_the_recorded_aspect_and_stays_even(loaded):
    props = props_of(loaded)
    assert props["height"] == 800  # 1280x800 recorded, 1280 wide composition
    assert props["height"] % 2 == 0


def test_a_missing_chapter_names_the_recording_command(loaded, tmp_path):
    (tmp_path / "media" / "demos" / "tour-a" / "demo.mp4").unlink()
    with pytest.raises(RuntimeError, match="--demo 3"):
        props_of(loaded)


def test_per_language_output_needs_a_placeholder(loaded):
    step = loaded.compose[0]
    with pytest.raises(RuntimeError, match="overwrite"):
        tour._output_path(step, "de")
    assert tour._output_path(step, None).name == "feature-tour.mp4"


def test_missing_node_is_an_actionable_error(monkeypatch):
    monkeypatch.setattr(tour.shutil, "which", lambda name: None)
    with pytest.raises(RuntimeError, match="needs Node.js"):
        tour._npx()


# --- the transcode that meets a budget ----------------------------------------


def test_bitrate_targets_the_budget_with_headroom():
    rate = video.bitrate_for(seconds=100, max_bytes=2_000_000)
    assert rate < 2_000_000 * 8 / 100  # leaves room for the container
    assert rate > 2_000_000 * 8 / 100 * 0.9


def test_bitrate_has_a_floor():
    assert video.bitrate_for(seconds=10_000, max_bytes=1000) == 100_000


def test_transcode_uses_a_bitrate_when_given_one(tmp_path, monkeypatch):
    calls = []
    monkeypatch.setattr(ffmpeg, "run", lambda args, cwd=None: calls.append(args))
    video.transcode_mp4(tmp_path / "in.mp4", {"bitrate": 800_000}, tmp_path / "out.mp4")
    args = calls[0]
    assert args[args.index("-b:v") + 1] == "800000"
    assert args[args.index("-maxrate") + 1] == "800000"
    assert "-crf" not in args


def test_transcode_falls_back_to_crf(tmp_path, monkeypatch):
    calls = []
    monkeypatch.setattr(ffmpeg, "run", lambda args, cwd=None: calls.append(args))
    video.transcode_mp4(tmp_path / "in.mp4", {"crf": 26, "width": 960}, tmp_path / "out.mp4")
    args = calls[0]
    assert args[args.index("-crf") + 1] == "26"
    assert "scale=960:-2:flags=lanczos" in args[args.index("-vf") + 1]
    assert args[args.index("-pix_fmt") + 1] == "yuv420p"
