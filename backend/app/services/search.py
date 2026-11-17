"""SearchService — embed → retrieve → attach metadata → filter → rank (PRD §9.2–9.4)."""

from __future__ import annotations

import time
from dataclasses import dataclass, field

import numpy as np
from PIL import Image

from .embedding import EmbeddingService
from .index import IndexService
from .metadata import MetadataService
from .query_parser import ParsedQuery, parse_query

# Image queries: only use a zero-shot attribute guess when CLIP is this sure.
INFERENCE_MIN_CONFIDENCE = 0.5


@dataclass
class RankingWeights:
    alpha: float
    beta: float


@dataclass
class RankedItem:
    position: int
    similarity: float
    attribute_match: float
    score: float
    reason: str | None = None


@dataclass
class SearchOutcome:
    items: list[RankedItem]
    detected: ParsedQuery
    filters: dict[str, list[str]]
    weights: RankingWeights
    candidates_considered: int
    latency_ms: float = 0.0
    extras: dict = field(default_factory=dict)


def attribute_match(meta: dict, targets: ParsedQuery) -> float:
    """Fraction of requested attribute groups (category, colour) the item satisfies."""
    checks = []
    if targets.categories:
        checks.append(meta.get("category_key") in targets.categories)
    if targets.colours:
        checks.append(meta.get("colour") in targets.colours)
    return float(np.mean(checks)) if checks else 0.0


class SearchService:
    def __init__(
        self,
        embedding: EmbeddingService,
        index: IndexService,
        metadata: MetadataService,
        default_weights: RankingWeights,
        candidate_multiplier: int = 4,
        text_index: IndexService | None = None,
    ):
        if index.size != len(metadata):
            raise ValueError(f"index has {index.size} vectors but metadata has {len(metadata)} items")
        if text_index is not None and (text_index.size != index.size or text_index.dim != index.dim):
            raise ValueError("text index is not aligned with the image index")
        self.embedding = embedding
        self.index = index
        # Dual index: when the image index holds fine-tuned (adapted) vectors, text queries
        # search the pretrained CLIP space instead, where text↔image alignment is best.
        self.text_index = text_index
        self.metadata = metadata
        self.default_weights = default_weights
        self.candidate_multiplier = candidate_multiplier

    # ------------------------------------------------------------------ public
    def search_text(
        self, query: str, top_k: int, filters: dict[str, list[str]], weights: RankingWeights | None = None
    ) -> SearchOutcome:
        t0 = time.perf_counter()
        vector = self.embedding.encode_text(query)
        detected = parse_query(query)
        out = self.rank(vector, top_k, filters, detected, weights or self.default_weights,
                        index=self.text_index or self.index)
        out.latency_ms = (time.perf_counter() - t0) * 1000
        return out

    def search_image(
        self,
        image: Image.Image,
        top_k: int,
        filters: dict[str, list[str]],
        weights: RankingWeights | None = None,
    ) -> SearchOutcome:
        t0 = time.perf_counter()
        raw, vector = self.embedding.encode_image_views(image)
        detected, guesses = self.infer_attributes(raw)
        out = self.rank(vector, top_k, filters, detected, weights or self.default_weights)
        out.extras["inferred"] = guesses
        out.latency_ms = (time.perf_counter() - t0) * 1000
        return out

    # --------------------------------------------------------------- internals
    def infer_attributes(self, vector: np.ndarray) -> tuple[ParsedQuery, dict]:
        """Zero-shot category/colour guess for an uploaded photo."""
        guesses: dict = {}
        detected = ParsedQuery()
        cat_keys = sorted(self.metadata.category_labels)
        if cat_keys:
            labels = [self.metadata.category_labels[k] for k in cat_keys]
            label, p = self.embedding.zero_shot(vector, "category", labels)
            key = cat_keys[labels.index(label)]
            guesses["category"] = {"value": key, "label": label, "confidence": round(p, 3)}
            if p >= INFERENCE_MIN_CONFIDENCE:
                detected.categories.add(key)
        colours = sorted(set(self.metadata.values("colour").tolist()) - {"multicolour", ""})
        if colours:
            label, p = self.embedding.zero_shot(vector, "colour", colours)
            guesses["colour"] = {"value": label, "label": label, "confidence": round(p, 3)}
            if p >= INFERENCE_MIN_CONFIDENCE:
                detected.colours.add(label)
        return detected, guesses

    def rank(
        self,
        vector: np.ndarray,
        top_k: int,
        filters: dict[str, list[str]],
        targets: ParsedQuery,
        weights: RankingWeights,
        exclude: set[int] | None = None,
        allowed: np.ndarray | None = None,
        index: IndexService | None = None,
    ) -> SearchOutcome:
        """Retrieve candidates from FAISS and order them by the blended final score."""
        exclude = exclude or set()
        active_filters = {k: v for k, v in filters.items() if v}
        filtered = self.metadata.matching_positions(active_filters)
        if allowed is not None:
            filtered = allowed if filtered is None else np.intersect1d(filtered, allowed)

        use_attributes = targets.has_attributes and weights.beta > 0
        # Over-fetch when re-ranking so attribute matches outside the raw top-k can rise.
        n_candidates = top_k * (self.candidate_multiplier if use_attributes else 1) + len(exclude)
        scores, positions = (index or self.index).search(vector, n_candidates, filtered)

        ranked: list[RankedItem] = []
        for sim, pos in zip(scores.tolist(), positions.tolist()):
            if pos in exclude:
                continue
            match = attribute_match(self.metadata.get(pos), targets) if use_attributes else 0.0
            final = weights.alpha * sim + weights.beta * match if use_attributes else sim
            ranked.append(RankedItem(pos, sim, match, final))
        ranked.sort(key=lambda r: r.score, reverse=True)

        return SearchOutcome(
            items=ranked[:top_k],
            detected=targets,
            filters=active_filters,
            weights=weights,
            candidates_considered=len(positions),
        )
