"""Generate a tiny DeepFashion2-*format* dataset of drawn garment silhouettes.

SMOKE-TEST DATA ONLY. It lets the full pipeline (crop → CLIP → FAISS → API → UI)
run on a laptop without downloading DeepFashion2. Metrics computed on it mean
nothing; real numbers come from the Kaggle run on the actual dataset.

    python ml/scripts/make_synthetic_df2.py --out /tmp/df2_synthetic --images 400
"""

from __future__ import annotations

import argparse
import json
import random
from pathlib import Path

from PIL import Image, ImageDraw, ImageFilter

COLOURS = {
    "black": (25, 25, 28), "white": (240, 240, 236), "grey": (128, 128, 132), "red": (200, 30, 40),
    "pink": (240, 140, 180), "orange": (240, 130, 30), "yellow": (240, 210, 40), "green": (40, 140, 70),
    "blue": (40, 100, 210), "navy": (20, 30, 90), "purple": (120, 50, 160), "brown": (110, 70, 40),
    "beige": (215, 195, 160),
}
UPPER = [1, 2, 3, 4, 5, 6]
LOWER = [7, 8, 9]
DRESS = [10, 11, 12, 13]


def shape(cat: int, x: int, y: int, w: int, h: int) -> list[list[tuple[float, float]]]:
    """Polygons for a garment inside box (x, y, w, h)."""
    cx = x + w / 2
    body_l, body_r = x + w * 0.25, x + w * 0.75
    if cat in UPPER:
        sleeve = {1: 0.35, 2: 0.9, 3: 0.35, 4: 0.9, 5: 0.0, 6: 0.0}[cat]
        polys = [[(body_l, y + h * 0.1), (body_r, y + h * 0.1), (body_r, y + h), (body_l, y + h)]]
        if sleeve:
            sl = h * sleeve
            polys.append([(body_l, y + h * 0.1), (x, y + h * 0.1 + sl), (x + w * 0.1, y + h * 0.1 + sl),
                          (body_l, y + h * 0.35)])
            polys.append([(body_r, y + h * 0.1), (x + w, y + h * 0.1 + sl), (x + w * 0.9, y + h * 0.1 + sl),
                          (body_r, y + h * 0.35)])
        if cat == 6:  # sling straps
            polys.append([(body_l + 4, y), (body_l + 10, y), (body_l + 10, y + h * 0.1), (body_l + 4, y + h * 0.1)])
            polys.append([(body_r - 10, y), (body_r - 4, y), (body_r - 4, y + h * 0.1), (body_r - 10, y + h * 0.1)])
        return polys
    if cat in (7, 8):
        leg = h if cat == 8 else h * 0.4
        return [
            [(body_l, y), (body_r, y), (body_r, y + h * 0.15), (body_l, y + h * 0.15)],
            [(body_l, y), (cx - 2, y), (cx - 4, y + leg), (body_l - 6, y + leg)],
            [(cx + 2, y), (body_r, y), (body_r + 6, y + leg), (cx + 4, y + leg)],
        ]
    if cat == 9:
        return [[(body_l, y), (body_r, y), (x + w * 0.9, y + h * 0.6), (x + w * 0.1, y + h * 0.6)]]
    # dresses
    sleeve = {10: 0.3, 11: 0.75, 12: 0.0, 13: 0.0}[cat]
    polys = [[(body_l, y + h * 0.05), (body_r, y + h * 0.05), (body_r, y + h * 0.35),
              (x + w * 0.95, y + h), (x + w * 0.05, y + h), (body_l, y + h * 0.35)]]
    if sleeve:
        sl = h * sleeve
        polys.append([(body_l, y + h * 0.05), (x, y + h * 0.05 + sl), (x + w * 0.1, y + h * 0.05 + sl),
                      (body_l, y + h * 0.2)])
        polys.append([(body_r, y + h * 0.05), (x + w, y + h * 0.05 + sl), (x + w * 0.9, y + h * 0.05 + sl),
                      (body_r, y + h * 0.2)])
    return polys


def draw_item(draw: ImageDraw.ImageDraw, cat: int, box, colour, jitter: random.Random):
    x, y, w, h = box
    for poly in shape(cat, x, y, w, h):
        pts = [(px + jitter.uniform(-2, 2), py + jitter.uniform(-2, 2)) for px, py in poly]
        draw.polygon(pts, fill=colour, outline=tuple(max(0, c - 40) for c in colour))
    xs = [p[0] for poly in shape(cat, x, y, w, h) for p in poly]
    ys = [p[1] for poly in shape(cat, x, y, w, h) for p in poly]
    return [int(min(xs)), int(min(ys)), int(max(xs)), int(max(ys))]


def render(outfit, source: str, rnd: random.Random) -> tuple[Image.Image, list]:
    bg = (250, 250, 250) if source == "shop" else tuple(rnd.randint(150, 230) for _ in range(3))
    img = Image.new("RGB", (320, 420), bg)
    draw = ImageDraw.Draw(img)
    boxes = []
    if len(outfit) == 1:
        cat, colour = outfit[0]
        boxes.append(draw_item(draw, cat, (40, 30, 240, 360), COLOURS[colour], rnd))
    else:
        (c1, col1), (c2, col2) = outfit
        boxes.append(draw_item(draw, c2, (60, 200, 200, 200), COLOURS[col2], rnd))
        boxes.append(draw_item(draw, c1, (40, 30, 240, 190), COLOURS[col1], rnd))
        boxes = boxes[::-1]
    if source == "user":
        img = img.rotate(rnd.uniform(-6, 6), fillcolor=bg).filter(ImageFilter.GaussianBlur(0.6))
    return img, boxes


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", type=Path, required=True)
    ap.add_argument("--images", type=int, default=400, help="images per split")
    ap.add_argument("--seed", type=int, default=0)
    a = ap.parse_args()
    rnd = random.Random(a.seed)
    names = list(COLOURS)
    for split, n in (("train", a.images), ("validation", max(40, a.images // 3))):
        (a.out / split / "image").mkdir(parents=True, exist_ok=True)
        (a.out / split / "annos").mkdir(parents=True, exist_ok=True)
        idx = 0
        pair = 0
        while idx < n:
            pair += 1
            if rnd.random() < 0.35:
                outfit = [(rnd.choice(DRESS), rnd.choice(names))]
            else:
                outfit = [(rnd.choice(UPPER), rnd.choice(names)), (rnd.choice(LOWER), rnd.choice(names))]
            for source in ("shop", "user", "user"):
                if idx >= n:
                    break
                idx += 1
                img, boxes = render(outfit, source, rnd)
                name = f"{idx:06d}"
                img.save(a.out / split / "image" / f"{name}.jpg", quality=90)
                anno = {"source": source, "pair_id": pair}
                for k, ((cat, _), box) in enumerate(zip(outfit, boxes), start=1):
                    anno[f"item{k}"] = {
                        "category_id": cat, "bounding_box": box, "style": 1,
                        "scale": 3, "occlusion": 1, "viewpoint": 1 if source == "shop" else 2, "zoom_in": 1,
                    }
                (a.out / split / "annos" / f"{name}.json").write_text(json.dumps(anno))
    print(f"wrote synthetic DeepFashion2-format data to {a.out}")


if __name__ == "__main__":
    main()
