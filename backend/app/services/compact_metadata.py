"""Columnar, low-memory storage for catalogue metadata (``metadata.npz``).

``metadata.json`` holds one dict per item; parsed, 50k of them cost ~250 MB of
Python objects. Here every field is a numpy column: strings with few distinct
values (category, colour, viewpoint …) are small integer codes into a vocabulary,
the rest are fixed-width arrays, and ``worn_with`` is a CSR pair of offsets +
positions. ``CompactItems`` behaves like the original list of dicts (``len``,
indexing, iteration), building each dict only when it is asked for.
"""

from __future__ import annotations

from collections.abc import Iterator, Sequence
from pathlib import Path

import numpy as np

CODED = ("category", "category_key", "colour", "source", "viewpoint", "occlusion", "scale", "zoom_in", "split")
FORMAT_VERSION = 1


def save_compact(items: list[dict], path: Path) -> None:
    n = len(items)
    cols: dict[str, np.ndarray] = {"format_version": np.array(FORMAT_VERSION)}
    for field in CODED:
        values = [str(it.get(field, "")) for it in items]
        vocab = sorted(set(values))
        index = {v: i for i, v in enumerate(vocab)}
        cols[f"{field}__vocab"] = np.array(vocab, dtype=str)
        cols[f"{field}__codes"] = np.array([index[v] for v in values], dtype=np.uint16)
    cols["item_id"] = np.array([it["item_id"] for it in items], dtype=str)
    cols["image_id"] = np.array([str(it.get("image_id", "")) for it in items], dtype=str)
    cols["colour_confidence"] = np.array([float(it.get("colour_confidence", 0.0)) for it in items], dtype=np.float32)
    cols["pair_id"] = np.array([int(it.get("pair_id", -1)) for it in items], dtype=np.int64)
    cols["style"] = np.array([int(it.get("style", 0)) for it in items], dtype=np.int16)
    pos_of = {it["item_id"]: i for i, it in enumerate(items)}
    offsets = np.zeros(n + 1, dtype=np.int64)
    flat: list[int] = []
    for i, it in enumerate(items):
        flat.extend(pos_of[w] for w in it.get("worn_with", []) if w in pos_of)
        offsets[i + 1] = len(flat)
    cols["worn_offsets"] = offsets
    cols["worn_positions"] = np.array(flat, dtype=np.int32)
    np.savez_compressed(path, **cols)


class CompactItems(Sequence):
    """Read-only list-of-dicts view over ``metadata.npz``."""

    def __init__(self, path: Path):
        with np.load(path, allow_pickle=False) as z:
            self._cols = {k: z[k] for k in z.files}
        self._n = len(self._cols["item_id"])

    def __len__(self) -> int:
        return self._n

    def column(self, field: str) -> np.ndarray:
        """All values of a coded field as a numpy string array (vectorised)."""
        return self._cols[f"{field}__vocab"][self._cols[f"{field}__codes"]]

    def item_ids(self) -> np.ndarray:
        return self._cols["item_id"]

    def __getitem__(self, pos):  # type: ignore[override]
        if isinstance(pos, slice):
            return [self[i] for i in range(*pos.indices(self._n))]
        i = int(pos)
        if i < 0:
            i += self._n
        if not 0 <= i < self._n:
            raise IndexError(pos)
        c = self._cols
        item = {f: str(c[f"{f}__vocab"][c[f"{f}__codes"][i]]) for f in CODED}
        lo, hi = int(c["worn_offsets"][i]), int(c["worn_offsets"][i + 1])
        item.update(
            position=i,
            item_id=str(c["item_id"][i]),
            image_id=str(c["image_id"][i]),
            colour_confidence=round(float(c["colour_confidence"][i]), 4),  # JSON stored 4 decimals
            pair_id=int(c["pair_id"][i]),
            style=int(c["style"][i]),
            worn_with=[str(c["item_id"][p]) for p in c["worn_positions"][lo:hi]],
        )
        return item

    def __iter__(self) -> Iterator[dict]:
        for i in range(self._n):
            yield self[i]
