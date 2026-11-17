"""IndexService — wraps FAISS. Returns positions and scores only (PRD §9.1)."""

from __future__ import annotations

from pathlib import Path

import faiss
import numpy as np

from .. import _platform


class IndexService:
    def __init__(self, index: faiss.Index):
        self.index = index

    @classmethod
    def load(cls, path: Path) -> IndexService:
        return cls(faiss.read_index(str(path)))

    @property
    def size(self) -> int:
        return int(self.index.ntotal)

    @property
    def dim(self) -> int:
        return int(self.index.d)

    def search(
        self, vector: np.ndarray, k: int, allowed: np.ndarray | None = None
    ) -> tuple[np.ndarray, np.ndarray]:
        """Top-``k`` inner-product search, optionally restricted to ``allowed`` positions.

        Restriction uses FAISS's ``IDSelectorBatch`` so filtered search is still exact
        and never degenerates into a Python loop.
        """
        if self.size == 0 or k <= 0:
            return np.empty(0, np.float32), np.empty(0, np.int64)
        if _platform.FAISS_SINGLE_THREAD:
            faiss.omp_set_num_threads(1)  # per-thread setting; this may be a threadpool worker
        query = np.ascontiguousarray(vector.reshape(1, -1), dtype=np.float32)
        if allowed is None:
            k = min(k, self.size)
            scores, ids = self.index.search(query, k)
        else:
            if len(allowed) == 0:
                return np.empty(0, np.float32), np.empty(0, np.int64)
            ids_arr = np.ascontiguousarray(allowed, dtype=np.int64)
            selector = faiss.IDSelectorBatch(ids_arr)
            params = faiss.SearchParameters(sel=selector)
            scores, ids = self.index.search(query, min(k, len(ids_arr)), params=params)
        keep = ids[0] >= 0
        return scores[0][keep], ids[0][keep]

    def vector(self, position: int) -> np.ndarray:
        return self.index.reconstruct(int(position))
