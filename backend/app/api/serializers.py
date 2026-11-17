"""Shape service objects into API schemas. Never exposes file-system paths."""

from __future__ import annotations

from ..schemas.api import ItemDetail, ItemSummary, ScoredItem
from ..services.metadata import MetadataService
from ..services.search import RankedItem


def image_url(item_id: str) -> str:
    return f"/images/{item_id}"


def summary(meta: dict) -> ItemSummary:
    return ItemSummary(
        item_id=meta["item_id"],
        image_url=image_url(meta["item_id"]),
        category=meta["category"],
        category_key=meta["category_key"],
        colour=meta.get("colour", "unknown"),
        source=meta.get("source", "unknown"),
        viewpoint=meta.get("viewpoint", "unknown"),
    )


def detail(meta: dict) -> ItemDetail:
    return ItemDetail(
        **summary(meta).model_dump(),
        occlusion=meta.get("occlusion", "unknown"),
        scale=meta.get("scale", "unknown"),
        zoom_in=meta.get("zoom_in", "unknown"),
        colour_confidence=float(meta.get("colour_confidence", 0.0)),
        pair_id=int(meta.get("pair_id", -1)),
        style=int(meta.get("style", 0)),
        worn_with=list(meta.get("worn_with", [])),
    )


def scored(items: list[RankedItem], metadata: MetadataService) -> list[ScoredItem]:
    return [
        ScoredItem(
            **summary(metadata.get(r.position)).model_dump(),
            score=round(r.score, 4),
            similarity=round(r.similarity, 4),
            attribute_match=round(r.attribute_match, 4),
            reason=r.reason,
        )
        for r in items
    ]
