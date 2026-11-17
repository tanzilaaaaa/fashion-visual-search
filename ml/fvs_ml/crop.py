"""Garment cropping from DeepFashion2 bounding boxes."""

from __future__ import annotations

from pathlib import Path

import cv2
import numpy as np
from PIL import Image


def padded_box(
    x1: float, y1: float, x2: float, y2: float,
    width: int, height: int, padding: float,
) -> tuple[int, int, int, int]:
    """Expand a box by ``padding`` × its size and clip it to the image."""
    pw, ph = (x2 - x1) * padding, (y2 - y1) * padding
    return (
        max(0, int(round(x1 - pw))),
        max(0, int(round(y1 - ph))),
        min(width, int(round(x2 + pw))),
        min(height, int(round(y2 + ph))),
    )


def crop_garment(
    image_path: Path, bbox: tuple[float, float, float, float], padding: float
) -> Image.Image:
    """Read an image with OpenCV, crop one garment and return it as RGB PIL."""
    bgr = cv2.imread(str(image_path), cv2.IMREAD_COLOR)
    if bgr is None:
        raise FileNotFoundError(f"Unreadable image: {image_path}")
    h, w = bgr.shape[:2]
    x1, y1, x2, y2 = padded_box(*bbox, width=w, height=h, padding=padding)
    if x2 - x1 < 2 or y2 - y1 < 2:
        raise ValueError(f"Degenerate crop for {image_path}: {bbox}")
    crop = cv2.cvtColor(bgr[y1:y2, x1:x2], cv2.COLOR_BGR2RGB)
    return Image.fromarray(np.ascontiguousarray(crop))


def save_thumbnail(img: Image.Image, out_path: Path, max_side: int) -> None:
    """Save a WebP thumbnail (what the deployed demo serves — never the source photo)."""
    out_path.parent.mkdir(parents=True, exist_ok=True)
    thumb = img.copy()
    thumb.thumbnail((max_side, max_side), Image.Resampling.LANCZOS)
    thumb.save(out_path, format="WEBP", quality=82, method=4)
