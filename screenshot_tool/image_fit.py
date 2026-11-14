"""Fit images to configured bounds and validate their saved dimensions."""

from io import BytesIO

from PIL import Image, ImageOps


def size_shortfall(label: str, size: tuple[int, int], minimum: tuple[int, int]) -> str | None:
    """Describe when an image is smaller than either required dimension."""
    width, height = size
    min_width, min_height = minimum
    if width >= min_width and height >= min_height:
        return None
    return (
        f"{label} is {width}x{height}, below the required minimum "
        f"{min_width}x{min_height} (window or monitor work area too small, "
        "or the app ignored width/height)"
    )


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
