"""Build and persist the deployable artifacts: FAISS index + metadata + manifest."""

from __future__ import annotations

import json
import time
from pathlib import Path

import faiss
import numpy as np
import pandas as pd

from .config import OCCLUSION, SCALE, VIEWPOINT, ZOOM_IN

METADATA_VERSION = 1


def build_flat_ip_index(vectors: np.ndarray) -> faiss.Index:
    """Exact cosine search: L2-normalise, then inner product == cosine similarity."""
    vecs = np.ascontiguousarray(vectors, dtype=np.float32)
    faiss.normalize_L2(vecs)
    index = faiss.IndexFlatIP(vecs.shape[1])
    index.add(vecs)
    return index


def write_text_index(vectors: np.ndarray, output_dir: Path, name: str = "text_index.faiss") -> dict:
    """Second, position-aligned index of *pretrained* CLIP vectors for text queries.

    Used when the main index holds fine-tuned (adapter) vectors: the adapter is trained
    for photo→photo matching, while text↔image alignment is best in the original space.
    """
    faiss.write_index(build_flat_ip_index(vectors), str(Path(output_dir) / name))
    return {"file": name, "space": "pretrained CLIP", "purpose": "text queries"}


def item_records(items: pd.DataFrame) -> list[dict]:
    """Position-ordered metadata. Record ``i`` describes FAISS vector ``i``."""
    # Items photographed together are a real "worn with" signal for Complete the Look.
    groups = items.groupby(["split", "image_id"])["item_id"].apply(list).to_dict()
    records = []
    for pos, row in enumerate(items.itertuples(index=False)):
        worn_with = [i for i in groups[(row.split, row.image_id)] if i != row.item_id]
        records.append({
            "position": pos,
            "item_id": row.item_id,
            "category": row.category,
            "category_key": row.category_key,
            "colour": row.colour,
            "colour_confidence": round(float(row.colour_confidence), 4),
            "source": row.source,
            "viewpoint": VIEWPOINT.get(int(row.viewpoint), "unknown"),
            "occlusion": OCCLUSION.get(int(row.occlusion), "unknown"),
            "scale": SCALE.get(int(row.scale), "unknown"),
            "zoom_in": ZOOM_IN.get(int(row.zoom_in), "unknown"),
            "pair_id": int(row.pair_id),
            "style": int(row.style),
            "split": row.split,
            "image_id": row.image_id,
            "worn_with": worn_with,
        })
    return records


def write_artifacts(
    items: pd.DataFrame,
    vectors: np.ndarray,
    output_dir: Path,
    manifest_extra: dict | None = None,
) -> dict:
    """Write ``index.faiss``, ``metadata.json`` and ``manifest.json``.

    ``items`` must contain ``colour`` / ``colour_confidence`` and be aligned
    row-for-row with ``vectors``.
    """
    if len(items) != len(vectors):
        raise ValueError(f"{len(items)} items vs {len(vectors)} vectors — misaligned")
    output_dir = Path(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    index = build_flat_ip_index(vectors)
    faiss.write_index(index, str(output_dir / "index.faiss"))

    records = item_records(items.reset_index(drop=True))
    with open(output_dir / "metadata.json", "w", encoding="utf-8") as fh:
        json.dump({"version": METADATA_VERSION, "items": records}, fh, separators=(",", ":"))

    manifest = {
        "built_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "item_count": int(index.ntotal),
        "dimension": int(index.d),
        "index_type": "IndexFlatIP",
        "category_counts": items["category_key"].value_counts().sort_index().to_dict(),
        "colour_counts": items["colour"].value_counts().sort_index().to_dict(),
        "source_counts": items["source"].value_counts().to_dict(),
        **(manifest_extra or {}),
    }
    with open(output_dir / "manifest.json", "w", encoding="utf-8") as fh:
        json.dump(manifest, fh, indent=2)
    return manifest
