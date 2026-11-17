"""Reproducible splitting into an indexed catalogue and a held-out evaluation slice."""

from __future__ import annotations

import numpy as np
import pandas as pd


def holdout_eval_slice(
    df: pd.DataFrame,
    fraction: float,
    max_images: int,
    seed: int,
) -> tuple[pd.DataFrame, pd.DataFrame]:
    """Carve a held-out slice from the *validation* split, grouped by ``pair_id``.

    Grouping by pair keeps a consumer photo and its matching shop photos on the
    same side of the split, which the consumer→shop Recall@K protocol needs.
    Returns ``(pool, eval_slice)``; the slice is never indexed or used for tuning.
    """
    val = df[df["split"] == "validation"]
    pairs = np.array(sorted(val["pair_id"].unique()))
    rng = np.random.default_rng(seed)
    rng.shuffle(pairs)
    n_pairs = max(1, int(len(pairs) * fraction))
    chosen = set(pairs[:n_pairs].tolist())

    eval_mask = (df["split"] == "validation") & df["pair_id"].isin(chosen)
    eval_slice = df[eval_mask]
    # Cap by image count so evaluation stays cheap on CPU.
    images = eval_slice[["split", "image_id"]].drop_duplicates()
    if len(images) > max_images:
        keep_pairs = (
            eval_slice.groupby("pair_id")["image_id"].nunique().sample(frac=1, random_state=seed)
        )
        keep_pairs = keep_pairs[keep_pairs.cumsum() <= max_images].index
        eval_slice = eval_slice[eval_slice["pair_id"].isin(keep_pairs)]

    pool = df[~eval_mask]
    return pool.reset_index(drop=True), eval_slice.reset_index(drop=True)


def balanced_quotas(counts: dict[str, int], target: int) -> dict[str, int]:
    """Water-filling: equal share per category, unused share redistributed.

    Rare classes (e.g. short sleeve outwear) cannot fill ``target / 13``; their
    leftover goes to the larger classes so the subset still reaches ``target``.
    """
    quotas = {k: 0 for k in counts}
    remaining = min(target, sum(counts.values()))
    open_cats = {k for k, v in counts.items() if v > 0}
    while remaining > 0 and open_cats:
        share = max(1, remaining // len(open_cats))
        for cat in sorted(open_cats):
            add = min(share, counts[cat] - quotas[cat], remaining)
            quotas[cat] += add
            remaining -= add
            if quotas[cat] >= counts[cat]:
                open_cats.discard(cat)
            if remaining == 0:
                break
    return quotas


def sample_working_subset(
    pool: pd.DataFrame, target: int, seed: int, key: str = "category_key"
) -> pd.DataFrame:
    counts = pool[key].value_counts().to_dict()
    quotas = balanced_quotas(counts, target)
    parts = [
        pool[pool[key] == cat].sample(n=n, random_state=seed)
        for cat, n in sorted(quotas.items())
        if n > 0
    ]
    subset = pd.concat(parts).sample(frac=1, random_state=seed)
    return subset.reset_index(drop=True)
