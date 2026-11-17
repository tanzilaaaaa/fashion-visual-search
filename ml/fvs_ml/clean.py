"""Conservative cleaning of DeepFashion2 item rows.

Removed: duplicate items, rows with missing essentials, unknown categories and
degenerate / tiny boxes. Kept on purpose: consumer photos, side/back views,
occluded garments and rare categories — real queries look like that.
"""

from __future__ import annotations

import pandas as pd

from .config import CATEGORIES


def clean_items(df: pd.DataFrame, min_box_side: int = 32) -> tuple[pd.DataFrame, dict]:
    report: dict[str, int] = {"input_rows": len(df)}
    out = df.copy()

    # Dedupe on the item key, not the whole row (list-valued columns are unhashable).
    before = len(out)
    out = out.drop_duplicates(subset=["item_id"])
    report["duplicates_removed"] = before - len(out)

    before = len(out)
    essentials = ["item_id", "image_relpath", "category_id",
                  "bbox_x1", "bbox_y1", "bbox_x2", "bbox_y2"]
    out = out.dropna(subset=essentials)
    report["missing_essentials_removed"] = before - len(out)

    before = len(out)
    out = out[out["category_id"].isin(CATEGORIES.keys())]
    report["unknown_category_removed"] = before - len(out)

    out = out.assign(
        bbox_width=out["bbox_x2"] - out["bbox_x1"],
        bbox_height=out["bbox_y2"] - out["bbox_y1"],
    )
    before = len(out)
    valid = (
        (out["bbox_width"] >= min_box_side)
        & (out["bbox_height"] >= min_box_side)
        & (out["bbox_x2"] > 0)
        & (out["bbox_y2"] > 0)
    )
    out = out[valid]
    report["invalid_or_tiny_bbox_removed"] = before - len(out)

    out["bbox_area"] = out["bbox_width"] * out["bbox_height"]
    out["bbox_aspect_ratio"] = out["bbox_width"] / out["bbox_height"]
    out = out.reset_index(drop=True)
    report["output_rows"] = len(out)
    return out, report
