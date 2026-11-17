"""Fine-tuned residual CLIP-Adapter, applied in numpy at query time.

Trained offline by ``ml/fvs_ml/finetune.py`` on DeepFashion2 consumer↔shop pairs
(the CLIP backbone stays frozen). The index stores adapted image vectors, so query
*images* must pass through the same adapter before search. Text queries do not:
the adapter was trained to stay aligned with CLIP's text space.

    z' = normalise( r · (W2 · gelu(W1 · z + b1) + b2) + (1 − r) · z )
"""

from __future__ import annotations

import math
from dataclasses import dataclass
from pathlib import Path

import numpy as np


def _gelu_tanh(x: np.ndarray) -> np.ndarray:
    return 0.5 * x * (1.0 + np.tanh(math.sqrt(2.0 / math.pi) * (x + 0.044715 * x**3)))


@dataclass(frozen=True)
class Adapter:
    W1: np.ndarray
    b1: np.ndarray
    W2: np.ndarray
    b2: np.ndarray
    ratio: float

    @classmethod
    def from_npz(cls, path: Path) -> Adapter:
        with np.load(path, allow_pickle=False) as d:
            a = cls(
                W1=d["W1"].astype(np.float32), b1=d["b1"].astype(np.float32),
                W2=d["W2"].astype(np.float32), b2=d["b2"].astype(np.float32),
                ratio=float(d["ratio"]),
            )
        if a.W1.shape[1] != a.W2.shape[0] or a.W1.shape[0] != a.W2.shape[1]:
            raise ValueError(f"adapter shapes inconsistent: W1 {a.W1.shape}, W2 {a.W2.shape}")
        return a

    @property
    def dim(self) -> int:
        return int(self.W1.shape[1])

    @property
    def hidden(self) -> int:
        return int(self.W1.shape[0])

    def apply(self, z: np.ndarray) -> np.ndarray:
        z = np.asarray(z, dtype=np.float32)
        h = _gelu_tanh(z @ self.W1.T + self.b1) @ self.W2.T + self.b2
        out = self.ratio * h + (1.0 - self.ratio) * z
        return (out / np.maximum(np.linalg.norm(out, axis=-1, keepdims=True), 1e-12)).astype(np.float32)
