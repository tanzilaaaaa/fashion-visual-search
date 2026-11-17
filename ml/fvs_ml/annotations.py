"""Load DeepFashion2 item-level annotations into one flat DataFrame.

DeepFashion2 stores one JSON file per image (``<split>/annos/000001.json``)::

    {"source": "user", "pair_id": 1,
     "item1": {"category_id": 1, "category_name": "short sleeve top",
               "bounding_box": [x1, y1, x2, y2], "style": 1, "scale": 2,
               "occlusion": 1, "viewpoint": 2, "zoom_in": 1, ...},
     "item2": {...}}

Each ``itemN`` becomes one row. Image file names repeat across splits
(``train/image/000001.jpg`` and ``validation/image/000001.jpg`` are different
photos), so every row is keyed by ``split`` + ``image_id`` and stores a path
relative to the dataset root — never a bare basename.
"""

from __future__ import annotations

import json
import os
from concurrent.futures import ProcessPoolExecutor
from pathlib import Path

import pandas as pd

from .config import CATEGORIES, slug

ITEM_COLUMNS = [
    "item_id", "split", "image_id", "item_index", "image_relpath",
    "source", "pair_id", "style", "category_id", "category", "category_key",
    "bbox_x1", "bbox_y1", "bbox_x2", "bbox_y2",
    "scale", "occlusion", "viewpoint", "zoom_in",
]


def normalise_split(name: str) -> str:
    n = name.lower()
    if n.startswith("train"):
        return "train"
    if n.startswith("val"):
        return "validation"
    if n.startswith("test"):
        return "test"
    return n


def discover_splits(dataset_root: Path) -> dict[str, tuple[Path, Path]]:
    """Find ``{split: (image_dir, annos_dir)}`` anywhere under ``dataset_root``.

    Kaggle mirrors nest the official layout differently (``train/annos`` vs
    ``DeepFashion2/train/train/annos``), so we search instead of assuming.
    """
    found: dict[str, tuple[Path, Path]] = {}
    for dirpath, dirnames, _ in os.walk(dataset_root):
        if "annos" in dirnames:
            parent = Path(dirpath)
            image_dir = next(
                (parent / d for d in ("image", "images") if (parent / d).is_dir()), None
            )
            if image_dir is None:
                continue
            split = normalise_split(parent.name)
            # Keep the shallowest match per split.
            if split not in found or len(parent.parts) < len(found[split][1].parts):
                found[split] = (image_dir, parent / "annos")
        # Never descend into the (huge) image/annotation folders themselves.
        dirnames[:] = [d for d in dirnames if d not in ("annos", "image", "images")]
    return found


def make_item_id(split: str, image_id: str, item_index: int) -> str:
    return f"{split[:5]}-{image_id}-{item_index}"


def _parse_one(args: tuple[str, str, str, str]) -> list[dict]:
    anno_path, split, image_rel_dir, image_ext = args
    image_id = Path(anno_path).stem
    try:
        with open(anno_path, encoding="utf-8") as fh:
            data = json.load(fh)
    except (OSError, json.JSONDecodeError):
        return []

    rows = []
    for key, item in data.items():
        if not key.startswith("item") or not isinstance(item, dict):
            continue
        try:
            item_index = int(key[4:])
            x1, y1, x2, y2 = (float(v) for v in item["bounding_box"][:4])
            cat_id = int(item["category_id"])
        except (KeyError, ValueError, TypeError):
            continue
        cat_name = CATEGORIES.get(cat_id, str(item.get("category_name", "")))
        rows.append({
            "item_id": make_item_id(split, image_id, item_index),
            "split": split,
            "image_id": image_id,
            "item_index": item_index,
            "image_relpath": f"{image_rel_dir}/{image_id}{image_ext}",
            "source": str(data.get("source", "unknown")),
            "pair_id": int(data.get("pair_id", -1)),
            "style": int(item.get("style", 0)),
            "category_id": cat_id,
            "category": cat_name,
            "category_key": slug(cat_name),
            "bbox_x1": x1, "bbox_y1": y1, "bbox_x2": x2, "bbox_y2": y2,
            "scale": int(item.get("scale", 0)),
            "occlusion": int(item.get("occlusion", 0)),
            "viewpoint": int(item.get("viewpoint", 0)),
            "zoom_in": int(item.get("zoom_in", 0)),
        })
    return rows


def load_items(
    dataset_root: Path,
    splits: tuple[str, ...] = ("train", "validation"),
    max_images_per_split: int | None = None,
    workers: int | None = None,
) -> pd.DataFrame:
    """Parse every annotation JSON of the requested splits into item rows."""
    dataset_root = Path(dataset_root)
    layout = discover_splits(dataset_root)
    missing = [s for s in splits if s not in layout]
    if missing:
        raise FileNotFoundError(
            f"Could not find split(s) {missing} under {dataset_root}. "
            f"Found: {sorted(layout)}"
        )

    jobs: list[tuple[str, str, str, str]] = []
    for split in splits:
        image_dir, annos_dir = layout[split]
        image_rel_dir = image_dir.relative_to(dataset_root).as_posix()
        annos = sorted(p for p in annos_dir.iterdir() if p.suffix == ".json")
        if max_images_per_split:
            annos = annos[:max_images_per_split]
        jobs.extend((str(p), split, image_rel_dir, ".jpg") for p in annos)

    rows: list[dict] = []
    with ProcessPoolExecutor(max_workers=workers) as pool:
        for chunk in pool.map(_parse_one, jobs, chunksize=512):
            rows.extend(chunk)

    return pd.DataFrame(rows, columns=ITEM_COLUMNS)


# --------------------------------------------------------------------------- #
# Kaggle "with dataframes" CSV support
# --------------------------------------------------------------------------- #
# Exact column names accepted for each field. Matching is exact (case-insensitive)
# on purpose: the original notebook's substring match mapped ``item_id`` to
# ``pair_id`` / ``category_id`` because both contain "id".
CSV_COLUMN_ALIASES: dict[str, tuple[str, ...]] = {
    "image_id": ("image_id", "image_name", "img_id", "file_name", "filename", "image"),
    "split": ("split", "set", "subset"),
    "item_index": ("item_index", "item_no", "item_number", "item"),
    "source": ("source",),
    "pair_id": ("pair_id",),
    "style": ("style",),
    "category_id": ("category_id",),
    "category": ("category_name", "category"),
    "bbox": ("bounding_box", "bbox"),
    "bbox_x1": ("x1", "xmin", "bbox_x1"),
    "bbox_y1": ("y1", "ymin", "bbox_y1"),
    "bbox_x2": ("x2", "xmax", "bbox_x2"),
    "bbox_y2": ("y2", "ymax", "bbox_y2"),
    "scale": ("scale",),
    "occlusion": ("occlusion",),
    "viewpoint": ("viewpoint",),
    "zoom_in": ("zoom_in",),
}


def map_csv_columns(columns: list[str]) -> dict[str, str]:
    lower = {c.lower().strip(): c for c in columns}
    mapping: dict[str, str] = {}
    for field_name, aliases in CSV_COLUMN_ALIASES.items():
        for alias in aliases:
            if alias in lower:
                mapping[field_name] = lower[alias]
                break
    return mapping
