"""RecommendationService — Find Similar and Complete the Look (PRD §5.4, §9.4).

Both modes reuse the catalogue's own embeddings, so every suggestion is
deterministic and comes with a short, human-readable reason.
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path

import numpy as np

from .query_parser import ParsedQuery
from .search import RankedItem, RankingWeights, SearchService

GROUP_LABELS = {"tops": "Tops", "bottoms": "Bottoms", "outerwear": "Outerwear", "dresses": "Dresses"}


class ItemNotFound(LookupError):
    pass


@dataclass
class CompatibilityMap:
    groups: dict[str, list[str]]
    pairs: dict[str, list[str]]

    @classmethod
    def load(cls, path: Path) -> CompatibilityMap:
        data = json.loads(Path(path).read_text(encoding="utf-8"))
        return cls(groups=data["groups"], pairs=data["pairs"])

    def group_of(self, category_key: str) -> str | None:
        return next((g for g, cats in self.groups.items() if category_key in cats), None)

    def targets(self, category_key: str) -> list[tuple[str, set[str]]]:
        group = self.group_of(category_key)
        if group is None:
            return []
        return [(g, set(self.groups[g])) for g in self.pairs.get(group, [])]


@dataclass
class LookGroup:
    group: str
    label: str
    items: list[RankedItem]


class RecommendationService:
    def __init__(self, search: SearchService, compatibility: CompatibilityMap):
        self.search = search
        self.compat = compatibility

    def _position(self, item_id: str) -> int:
        pos = self.search.metadata.position_of(item_id)
        if pos is None:
            raise ItemNotFound(item_id)
        return pos

    def similar(self, item_id: str, top_k: int, filters: dict[str, list[str]] | None = None) -> list[RankedItem]:
        pos = self._position(item_id)
        source = self.search.metadata.get(pos)
        vector = self.search.index.vector(pos)
        out = self.search.rank(
            vector, top_k, filters or {}, ParsedQuery(), RankingWeights(1.0, 0.0), exclude={pos}
        )
        for r in out.items:
            same_cat = self.search.metadata.get(r.position)["category_key"] == source["category_key"]
            r.reason = "Similar visual style" + (", same category" if same_cat else "")
        return out.items

    def complete_the_look(self, item_id: str, per_group: int) -> tuple[dict, list[LookGroup]]:
        pos = self._position(item_id)
        source = self.search.metadata.get(pos)
        vector = self.search.index.vector(pos)
        worn_with = set(source.get("worn_with", []))
        source_label = source["category"]

        groups: list[LookGroup] = []
        for group, categories in self.compat.targets(source["category_key"]):
            allowed = self.search.metadata.positions_in_categories(categories)
            out = self.search.rank(
                vector, per_group * 2, {}, ParsedQuery(), RankingWeights(1.0, 0.0),
                exclude={pos}, allowed=allowed,
            )
            # Garments photographed together are real outfit evidence: always include
            # them (even beyond the similarity cut-off) and list them first.
            pinned = []
            for other_id in worn_with:
                other = self.search.metadata.position_of(other_id)
                if other is None or self.search.metadata.get(other)["category_key"] not in categories:
                    continue
                sim = float(self.search.index.vector(other) @ vector)
                pinned.append(RankedItem(other, sim, 0.0, sim, f"Worn with this {source_label} in the same photo"))
            pinned_pos = {p.position for p in pinned}
            rest = [r for r in out.items if r.position not in pinned_pos]
            for r in rest:
                r.reason = f"Complements this {source_label} — matching colour and style"
            items = sorted(pinned, key=lambda r: r.score, reverse=True) + rest
            groups.append(LookGroup(group, GROUP_LABELS.get(group, group.title()), items[:per_group]))
        return source, groups


# --------------------------------------------------------------------------- #
# "For you" — personal recommendations from favorites + interests
# --------------------------------------------------------------------------- #
@dataclass
class ForYouSection:
    key: str
    title: str
    items: list[RankedItem]


def _mean_unit(vectors: np.ndarray, weights: np.ndarray) -> np.ndarray:
    v = (vectors * weights[:, None]).sum(axis=0)
    return (v / max(float(np.linalg.norm(v)), 1e-12)).astype(np.float32)


def for_user(
    rec: RecommendationService,
    favorite_ids: list[str],
    categories: list[str],
    colours: list[str],
    styles: list[str],
    top_k: int = 12,
) -> list[ForYouSection]:
    """Up to two sections, each item carrying a human-readable reason.

    1. "Because you liked…": a taste vector (recency-weighted mean of the latest
       20 favorites' image-index vectors) searched in the photo index, with the
       chosen categories/colours as the attribute bonus. Each pick names the
       favorite it is closest to.
    2. "Picked for your interests": a sentence built from the interests, searched
       in the text index (pretrained CLIP space, where words match best).
    Favorites and items already shown in section 1 are never repeated.
    """
    search, meta = rec.search, rec.search.metadata
    targets = ParsedQuery(set(categories), set(colours))
    weights = search.default_weights
    sections: list[ForYouSection] = []

    fav_pos = [p for p in (meta.position_of(i) for i in favorite_ids) if p is not None]
    shown: set[int] = set(fav_pos)

    if fav_pos:
        recent = fav_pos[:20]  # favorite_ids are newest first
        vecs = np.stack([search.index.vector(p) for p in recent])
        recency = np.linspace(1.0, 0.5, num=len(recent), dtype=np.float32)
        out = search.rank(_mean_unit(vecs, recency), top_k, {}, targets, weights, exclude=set(shown))
        for r in out.items:
            sims = vecs @ search.index.vector(r.position)
            closest = meta.get(recent[int(np.argmax(sims))])
            r.reason = f"Because you liked this {closest['category']}"
            shown.add(r.position)
        if out.items:
            sections.append(ForYouSection("favorites", "Because you liked…", out.items))

    if categories or colours or styles:
        cat_labels = [meta.category_labels.get(c, c.replace("_", " ")) for c in categories]
        words = [*styles, *colours]
        sentence = f"a photo of {' '.join(words)} {' or '.join(cat_labels) or 'clothing'}".replace("  ", " ")
        vector = search.embedding.encode_text(sentence)
        out = search.rank(vector, top_k, {}, targets, weights, exclude=set(shown),
                          index=search.text_index or search.index)
        why = " · ".join([*colours, *[c.replace("_", " ") for c in categories], *styles][:5])
        for r in out.items:
            r.reason = f"Matches your interest in {why}"
        if out.items:
            sections.append(ForYouSection("interests", "Picked for your interests", out.items))

    return sections
