"""Zero-shot colour tagging with CLIP.

DeepFashion2 has no colour labels, but the PRD's attribute filters and ranking
signal need one. CLIP already places images and colour words in one space, so
each item is tagged by comparing its image vector with an ensemble of colour
prompts — no extra model and no extra training.
"""

from __future__ import annotations

import numpy as np

from .config import COLOUR_MIN_CONFIDENCE, COLOURS

COLOUR_TEMPLATES = [
    "a photo of a {} piece of clothing.",
    "a {} garment.",
    "a person wearing {} clothes.",
    "{} colored fabric.",
]


def colour_prototypes(encode_texts) -> np.ndarray:
    """Average the template embeddings per colour → ``[len(COLOURS), D]`` (unit norm)."""
    protos = []
    for colour in COLOURS:
        emb = encode_texts([t.format(colour) for t in COLOUR_TEMPLATES])
        mean = emb.mean(axis=0)
        protos.append(mean / np.linalg.norm(mean))
    return np.stack(protos).astype(np.float32)


def tag_colours(
    vectors: np.ndarray, prototypes: np.ndarray, temperature: float = 100.0
) -> tuple[list[str], np.ndarray]:
    """Return (colour label, confidence) per vector; low confidence → 'multicolour'."""
    logits = temperature * vectors @ prototypes.T
    logits -= logits.max(axis=1, keepdims=True)
    probs = np.exp(logits)
    probs /= probs.sum(axis=1, keepdims=True)
    best = probs.argmax(axis=1)
    conf = probs[np.arange(len(best)), best]
    labels = [
        COLOURS[b] if c >= COLOUR_MIN_CONFIDENCE else "multicolour"
        for b, c in zip(best, conf)
    ]
    return labels, conf.astype(np.float32)
