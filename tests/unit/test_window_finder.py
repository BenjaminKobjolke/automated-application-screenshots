"""Unit tests for work-area clamping of the demo window position."""

from screenshot_tool.window_finder import clamp_to_work_area

# Work area of a 1920x1080 monitor with a 48px taskbar at the bottom
WORK = (0, 0, 1920, 1032)


def test_window_inside_work_area_keeps_position():
    assert clamp_to_work_area((100, 100, 740, 520), WORK) == (100, 100)


def test_window_under_taskbar_is_shifted_up():
    # 640x960 portrait window ending at y=1060, below the 1032 work-area edge
    assert clamp_to_work_area((100, 100, 740, 1060), WORK) == (100, 1032 - 960)


def test_window_past_right_edge_is_shifted_left():
    assert clamp_to_work_area((1800, 100, 2440, 520), WORK) == (1920 - 640, 100)


def test_window_past_left_and_top_is_shifted_into_bounds():
    assert clamp_to_work_area((-50, -20, 590, 400), WORK) == (0, 0)


def test_window_taller_than_work_area_is_pinned_to_top():
    assert clamp_to_work_area((100, 200, 740, 1400), WORK) == (100, 0)


def test_work_area_with_offset_origin():
    # Secondary monitor whose work area does not start at (0, 0)
    work = (1920, 0, 3840, 1032)
    assert clamp_to_work_area((1000, 100, 1640, 520), work) == (1920, 100)
