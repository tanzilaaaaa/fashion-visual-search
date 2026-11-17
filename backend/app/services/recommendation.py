"""RecommendationService — Find Similar and Complete the Look (PRD §5.4, §9.4).

Both modes reuse the catalogue's own embeddings, so every suggestion is
deterministic and comes with a short, human-readable reason.
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path

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
