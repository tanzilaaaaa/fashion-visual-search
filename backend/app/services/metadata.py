"""MetadataService — FAISS position ⇄ DeepFashion2 item, plus the filter vocabulary."""

from __future__ import annotations

import json
from pathlib import Path

import numpy as np

from .compact_metadata import CompactItems

# Filterable fields exposed to the UI and their human labels.
FILTER_FIELDS = {
    "category": ("category_key", "Category"),
    "colour": ("colour", "Colour"),
    "source": ("source", "Photo type"),
    "viewpoint": ("viewpoint", "Viewpoint"),
}
SOURCE_LABELS = {"shop": "Shop / product photo", "user": "Street / consumer photo"}


class UnknownFilterValue(ValueError):
    def __init__(self, field: str, values: list[str]):
        super().__init__(f"Unsupported value(s) for filter '{field}': {', '.join(values)}")
        self.field = field
        self.values = values


class MetadataService:
    def __init__(self, items: list[dict] | CompactItems):
        self.items = items
        if isinstance(items, CompactItems):
            # Columnar fast path: no per-item dicts are built at start-up.
            ids = items.item_ids()
            self.by_item_id = {str(item_id): i for i, item_id in enumerate(ids)}
            self._columns = {field: items.column(key).astype(object) for field, (key, _) in FILTER_FIELDS.items()}
            keys, labels = items.column("category_key"), items.column("category")
            self.category_labels = {str(k): str(v) for k, v in zip(keys, labels)}
            return
        for expected, item in enumerate(items):
            if item.get("position", expected) != expected:
                raise ValueError("metadata positions are not contiguous — index/lookup drift")
        self.by_item_id = {it["item_id"]: i for i, it in enumerate(items)}
        self._columns = {
            field: np.array([str(it.get(key, "")) for it in items], dtype=object)
            for field, (key, _) in FILTER_FIELDS.items()
        }
        self.category_labels = {it["category_key"]: it["category"] for it in items}

    @classmethod
    def load(cls, path: Path) -> MetadataService:
        """Prefer the compact ``metadata.npz`` next to ``path`` (written at build time)."""
        compact = Path(path).with_suffix(".npz")
        if compact.exists():
            return cls(CompactItems(compact))
        with open(path, encoding="utf-8") as fh:
            data = json.load(fh)
        return cls(data["items"] if isinstance(data, dict) else data)

    def __len__(self) -> int:
        return len(self.items)

    def get(self, position: int) -> dict:
        return self.items[int(position)]

    def position_of(self, item_id: str) -> int | None:
        return self.by_item_id.get(item_id)

    def values(self, field: str) -> np.ndarray:
        return self._columns[field]

    def vocabulary(self) -> dict[str, dict]:
        vocab = {}
        for field, (_, label) in FILTER_FIELDS.items():
            vals, counts = np.unique(self._columns[field], return_counts=True)
            options = []
            for v, c in sorted(zip(vals, counts), key=lambda t: (-t[1], t[0])):
                if field == "category":
                    text = self.category_labels.get(v, v)
                elif field == "source":
                    text = SOURCE_LABELS.get(v, v)
                else:
                    text = v
                options.append({"value": v, "label": text.capitalize(), "count": int(c)})
            if field == "category":
                options.sort(key=lambda o: o["label"])
            vocab[field] = {"label": label, "options": options}
        return vocab

    def matching_positions(self, filters: dict[str, list[str]]) -> np.ndarray | None:
        """Positions satisfying every filter (OR within a field, AND across fields).

        Returns ``None`` when no filter is active. Unknown values raise — the PRD
        requires unsupported filters to be rejected, not silently ignored.
        """
        mask = None
        for field, wanted in filters.items():
            if not wanted:
                continue
            if field not in self._columns:
                raise UnknownFilterValue(field, wanted)
            col = self._columns[field]
            known = set(col.tolist())
            unknown = [w for w in wanted if w not in known]
            if unknown:
                raise UnknownFilterValue(field, unknown)
            m = np.isin(col, wanted)
            mask = m if mask is None else mask & m
        return None if mask is None else np.flatnonzero(mask)

    def positions_in_categories(self, category_keys: set[str]) -> np.ndarray:
        return np.flatnonzero(np.isin(self._columns["category"], list(category_keys)))
