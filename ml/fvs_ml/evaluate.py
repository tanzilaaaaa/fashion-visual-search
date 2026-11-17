"""Offline evaluation: retrieval quality, text search precision, outfit pairing, footprint.

Metrics (PRD §12.3):
* **Consumer→shop Recall@1/5/10** on the held-out validation slice, using the
  DeepFashion2 retrieval protocol: a consumer ("user") item matches a shop item
  when both share ``pair_id`` and the same non-zero ``style``.
* **Baseline**: same-category matching in random order — what a tag-only
  catalogue can do with the same query.
* **Text→image Precision@K** over the indexed catalogue for natural phrasings
  (including synonyms such as "jeans" or "tank top"), against a keyword baseline
  that matches query words to category names.
* **Outfit co-occurrence Hit@10** for Complete the Look: garments photographed
  together in the held-out slice are treated as known-good pairs.
* **Footprint**: index / metadata / image bytes.
"""

from __future__ import annotations

import json
from pathlib import Path

import faiss
import numpy as np
import pandas as pd

KS = (1, 5, 10)

# Natural-language probes. Keys are the categories that count as relevant.
TEXT_PROBES: list[tuple[str, list[str]]] = [
    ("a plain white t-shirt", ["short_sleeve_top"]),
    ("short sleeve top", ["short_sleeve_top"]),
    ("a cosy long sleeve sweater", ["long_sleeve_top"]),
    ("long sleeve top", ["long_sleeve_top"]),
    ("a denim jacket", ["long_sleeve_outwear", "short_sleeve_outwear"]),
    ("a long winter coat", ["long_sleeve_outwear"]),
    ("a tank top", ["vest", "sling"]),
    ("a strappy camisole", ["sling", "vest"]),
    ("blue jeans", ["trousers"]),
    ("trousers", ["trousers"]),
    ("denim shorts", ["shorts"]),
    ("a pleated mini skirt", ["skirt"]),
    ("a red casual summer dress", ["short_sleeve_dress", "vest_dress", "sling_dress"]),
    ("an elegant long sleeve dress", ["long_sleeve_dress"]),
    ("a slip dress with thin straps", ["sling_dress"]),
    ("a black sleeveless dress", ["vest_dress", "sling_dress"]),
]


def recall_at_k(ranked_hits: np.ndarray, ks=KS) -> dict[str, float]:
    """``ranked_hits[q, r]`` is True if result ``r`` of query ``q`` is relevant."""
    return {f"recall@{k}": float(ranked_hits[:, :k].any(axis=1).mean()) for k in ks}


def precision_at_k(ranked_hits: np.ndarray, ks=KS) -> dict[str, float]:
    return {f"precision@{k}": float(ranked_hits[:, :k].mean()) for k in ks}


# --------------------------------------------------------------------------- #
# Consumer → shop
# --------------------------------------------------------------------------- #
def consumer_to_shop(items: pd.DataFrame, vectors: np.ndarray, seed: int = 0) -> dict:
    items = items.reset_index(drop=True)
    gallery_mask = (items["source"] == "shop").to_numpy()
    g_idx = np.flatnonzero(gallery_mask)
    g_keys = set(zip(items.loc[g_idx, "pair_id"], items.loc[g_idx, "style"]))

    q_mask = (
        (items["source"] == "user")
        & (items["style"] > 0)
        & pd.Series(list(zip(items["pair_id"], items["style"]))).isin(g_keys)
    ).to_numpy()
    q_idx = np.flatnonzero(q_mask)
    if len(q_idx) == 0 or len(g_idx) == 0:
        return {"queries": 0, "gallery": int(len(g_idx))}

    index = faiss.IndexFlatIP(vectors.shape[1])
    index.add(np.ascontiguousarray(vectors[g_idx], dtype=np.float32))
    kmax = max(KS)
    _, nn = index.search(np.ascontiguousarray(vectors[q_idx], dtype=np.float32), kmax)

    g_pair = items.loc[g_idx, "pair_id"].to_numpy()
    g_style = items.loc[g_idx, "style"].to_numpy()
    g_cat = items.loc[g_idx, "category_key"].to_numpy()
    q_pair = items.loc[q_idx, "pair_id"].to_numpy()
    q_style = items.loc[q_idx, "style"].to_numpy()
    q_cat = items.loc[q_idx, "category_key"].to_numpy()

    hits = (g_pair[nn] == q_pair[:, None]) & (g_style[nn] == q_style[:, None])

    # Baseline: same-category gallery items in random order.
    rng = np.random.default_rng(seed)
    base_hits = np.zeros((len(q_idx), kmax), dtype=bool)
    for qi in range(len(q_idx)):
        same = np.flatnonzero(g_cat == q_cat[qi])
        rng.shuffle(same)
        top = same[:kmax]
        base_hits[qi, : len(top)] = (g_pair[top] == q_pair[qi]) & (g_style[top] == q_style[qi])

    return {
        "queries": int(len(q_idx)),
        "gallery": int(len(g_idx)),
        "clip": recall_at_k(hits),
        "category_baseline": recall_at_k(base_hits),
    }


# --------------------------------------------------------------------------- #
# Text → image
# --------------------------------------------------------------------------- #
def keyword_categories(query: str, category_keys: list[str]) -> list[str]:
    words = set(query.lower().replace("-", " ").split())
    return [c for c in category_keys if set(c.split("_")) <= words]


def text_to_image(
    catalogue: pd.DataFrame, vectors: np.ndarray, encode_texts, k: int = 10, seed: int = 0
) -> dict:
    cats = catalogue["category_key"].to_numpy()
    category_keys = sorted(set(cats))
    index = faiss.IndexFlatIP(vectors.shape[1])
    index.add(np.ascontiguousarray(vectors, dtype=np.float32))
    q = encode_texts([p for p, _ in TEXT_PROBES])
    _, nn = index.search(np.ascontiguousarray(q, dtype=np.float32), k)

    rng = np.random.default_rng(seed)
    clip_rows, base_rows, per_query = [], [], []
    for (prompt, relevant), row in zip(TEXT_PROBES, nn):
        rel = np.isin(cats[row], relevant)
        matched = keyword_categories(prompt, category_keys)
        pool = np.flatnonzero(np.isin(cats, matched)) if matched else np.array([], dtype=int)
        rng.shuffle(pool)
        base = np.zeros(k, dtype=bool)
        base[: min(k, len(pool))] = np.isin(cats[pool[:k]], relevant)
        clip_rows.append(rel)
        base_rows.append(base)
        per_query.append({
            "query": prompt,
            "clip_precision@10": float(rel.mean()),
            "keyword_precision@10": float(base.mean()),
        })
    return {
        "clip": precision_at_k(np.array(clip_rows), ks=(1, 5, k)),
        "keyword_baseline": precision_at_k(np.array(base_rows), ks=(1, 5, k)),
        "per_query": per_query,
    }


# --------------------------------------------------------------------------- #
# Complete the Look
# --------------------------------------------------------------------------- #
def load_compatibility(path: Path) -> dict[str, set[str]]:
    data = json.loads(Path(path).read_text())
    group_of = {c: g for g, cs in data["groups"].items() for c in cs}
    return {
        cat: {c for g in data["pairs"][group_of[cat]] for c in data["groups"][g]}
        for cat in group_of
    }


def outfit_cooccurrence(
    items: pd.DataFrame, vectors: np.ndarray, compat: dict[str, set[str]], k: int = 10, seed: int = 0
) -> dict:
    items = items.reset_index(drop=True)
    cats = items["category_key"].to_numpy()
    photo = (items["split"] + "/" + items["image_id"]).to_numpy()
    rng = np.random.default_rng(seed)
    hits, base_hits = [], []
    for i in range(len(items)):
        targets = compat.get(cats[i], set())
        partners = np.flatnonzero((photo == photo[i]) & np.isin(cats, list(targets)))
        if len(partners) == 0:
            continue
        cand = np.flatnonzero(np.isin(cats, list(targets)) & (photo != photo[i]))
        cand = np.concatenate([cand, partners])
        scores = vectors[cand] @ vectors[i]
        top = cand[np.argsort(-scores)[:k]]
        hits.append(bool(np.isin(top, partners).any()))
        rnd = rng.permutation(cand)[:k]
        base_hits.append(bool(np.isin(rnd, partners).any()))
    return {
        "queries": len(hits),
        "clip_hit@10": float(np.mean(hits)) if hits else None,
        "random_hit@10": float(np.mean(base_hits)) if base_hits else None,
        "note": "Partners share a photo, so lighting/background can inflate this score; "
                "treat it as a sanity check alongside manual review.",
    }


def footprint(artifact_dir: Path) -> dict:
    artifact_dir = Path(artifact_dir)

    def size(p: Path) -> int:
        if p.is_file():
            return p.stat().st_size
        return sum(f.stat().st_size for f in p.rglob("*") if f.is_file()) if p.exists() else 0

    return {
        "index_bytes": size(artifact_dir / "index.faiss"),
        "metadata_bytes": size(artifact_dir / "metadata.json"),
        "images_bytes": size(artifact_dir / "images"),
    }
