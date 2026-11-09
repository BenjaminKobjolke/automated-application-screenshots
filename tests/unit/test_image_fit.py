"""Tests for shrinking images to a configured output box."""

from io import BytesIO

from PIL import Image

from screenshot_tool.image_fit import fit_png_within, fit_within


def _png(size: tuple[int, int]) -> bytes:
    buffer = BytesIO()
    Image.new("RGB", size).save(buffer, format="PNG")
    return buffer.getvalue()


def test_fit_within_shrinks_4k_image_to_full_hd():
    image = Image.new("RGB", (3840, 2160))

    fitted = fit_within(image, (1920, 1080))

    assert fitted.size == (1920, 1080)


def test_fit_within_preserves_aspect_ratio_inside_box():
    image = Image.new("RGB", (3840, 2141))

    fitted = fit_within(image, (1920, 1080))

    assert fitted.width == 1920
    assert fitted.height == 1070
    assert fitted.width <= 1920
    assert fitted.height <= 1080


def test_fit_within_returns_smaller_image_unchanged():
    image = Image.new("RGB", (1280, 800))

    fitted = fit_within(image, (1920, 1080))

    assert fitted is image
    assert fitted.size == (1280, 800)


def test_fit_png_within_keeps_smaller_png_bytes_identical():
    png = _png((1280, 800))

    assert fit_png_within(png, (1920, 1080)) == png


def test_fit_png_within_shrinks_oversized_png():
    png = _png((3840, 2160))

    fitted = fit_png_within(png, (1920, 1080))

    with Image.open(BytesIO(fitted)) as image:
        assert image.size == (1920, 1080)
