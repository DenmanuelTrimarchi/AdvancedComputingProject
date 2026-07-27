"""Strict, bounded image loading shared by every experiment script.

Mirrors the ownership rules used by the sister project's face service:
byte-bounded before decoding, pixel-bounded after decoding, EXIF orientation
normalised, animated/multi-frame images rejected, and every failure is a
specific, catchable exception rather than a silent skip.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

import numpy as np
from PIL import Image, ImageOps

from .config import (
    DEFAULT_MAX_IMAGE_BYTES,
    DEFAULT_MAX_IMAGE_PIXELS,
    HARD_MAX_IMAGE_BYTES,
    HARD_MAX_IMAGE_PIXELS,
)


class ImageLoadError(RuntimeError):
    """Raised for any image that cannot be safely and strictly loaded."""


@dataclass(frozen=True)
class LoadedImage:
    bgr: np.ndarray  # HxWx3 uint8, OpenCV's BGR channel order
    width: int
    height: int
    source_path: Path


def load_image_bgr(
    path: Path,
    *,
    max_bytes: int = DEFAULT_MAX_IMAGE_BYTES,
    max_pixels: int = DEFAULT_MAX_IMAGE_PIXELS,
) -> LoadedImage:
    if max_bytes > HARD_MAX_IMAGE_BYTES:
        raise ImageLoadError(f"max_bytes {max_bytes} exceeds hard ceiling {HARD_MAX_IMAGE_BYTES}")
    if max_pixels > HARD_MAX_IMAGE_PIXELS:
        raise ImageLoadError(f"max_pixels {max_pixels} exceeds hard ceiling {HARD_MAX_IMAGE_PIXELS}")

    path = Path(path)
    if not path.is_file():
        raise ImageLoadError(f"Image file does not exist: {path}")

    size = path.stat().st_size
    if size == 0:
        raise ImageLoadError(f"Image file is empty: {path}")
    if size > max_bytes:
        raise ImageLoadError(f"Image file {path} is {size} bytes, exceeds max_bytes={max_bytes}")

    try:
        with Image.open(path) as raw:
            raw.load()
            if getattr(raw, "is_animated", False):
                raise ImageLoadError(f"Animated/multi-frame images are not supported: {path}")
            oriented = ImageOps.exif_transpose(raw)
            if oriented is None:
                raise ImageLoadError(f"Failed to normalise EXIF orientation for: {path}")
            width, height = oriented.size
            if width * height > max_pixels:
                raise ImageLoadError(
                    f"Image {path} has {width * height} pixels, exceeds max_pixels={max_pixels}"
                )
            rgb = oriented.convert("RGB")
            array = np.asarray(rgb, dtype=np.uint8)
    except ImageLoadError:
        raise
    except Exception as exc:  # noqa: BLE001 - normalise every decode failure into ImageLoadError
        raise ImageLoadError(f"Could not decode image {path}: {exc}") from exc

    bgr = np.ascontiguousarray(array[:, :, ::-1])
    return LoadedImage(bgr=bgr, width=width, height=height, source_path=path)
