"""Shrink images to fit within a configured output size."""

from io import BytesIO

from PIL import Image, ImageOps


def fit_within(image: Image.Image, size: tuple[int, int]) -> Image.Image:
    """Return an image fitted inside ``size`` without enlarging smaller images."""
    if image.width <= size[0] and image.height <= size[1]:
        return image
    return ImageOps.contain(image, size, Image.Resampling.LANCZOS)


def fit_png_within(png: bytes, size: tuple[int, int]) -> bytes:
    """Shrink PNG bytes to ``size``, preserving original bytes when they fit."""
    with Image.open(BytesIO(png)) as image:
        if image.width <= size[0] and image.height <= size[1]:
            return png
        fitted = fit_within(image, size)
        output = BytesIO()
        fitted.save(output, format="PNG")
        return output.getvalue()
