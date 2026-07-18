"""Unit test for screenshot saving (directory creation + PNG write)."""

from PIL import Image

from screenshot_tool.capture import WindowCapture


def test_save_creates_language_subfolders(tmp_path):
    image = Image.new("RGB", (4, 4), "red")
    output_path = tmp_path / "screenshots" / "de" / "main.png"

    WindowCapture.save_screenshot(image, output_path)

    assert output_path.is_file()
    assert Image.open(output_path).size == (4, 4)
