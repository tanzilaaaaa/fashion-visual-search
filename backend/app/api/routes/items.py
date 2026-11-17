"""Item detail, Find Similar and Complete the Look."""

from __future__ import annotations

from fastapi import APIRouter, Depends, Path, Query
from fastapi.concurrency import run_in_threadpool

from ...schemas.api import ItemDetail, LookGroupOut, RecommendationsResponse, SimilarResponse
from ...services.recommendation import ItemNotFound, RecommendationService
from .. import serializers
from ..deps import get_recommendation, require_session
from ..errors import not_found

router = APIRouter(prefix="/items", tags=["items"], dependencies=[Depends(require_session)])

ItemId = Path(..., pattern=r"^[A-Za-z0-9_-]{1,64}$", description="Catalogue item id")


@router.get("/{item_id}", response_model=ItemDetail, summary="Item detail")
def get_item(item_id: str = ItemId, rec: RecommendationService = Depends(get_recommendation)):
    pos = rec.search.metadata.position_of(item_id)
    if pos is None:
        raise not_found(f"No item with id '{item_id}'.")
    return serializers.detail(rec.search.metadata.get(pos))


@router.get("/{item_id}/similar", response_model=SimilarResponse, summary="Find Similar")
async def similar(
    item_id: str = ItemId,
    top_k: int = Query(12, ge=1, le=100),
    rec: RecommendationService = Depends(get_recommendation),
):
    try:
        items = await run_in_threadpool(rec.similar, item_id, top_k)
    except ItemNotFound as exc:
        raise not_found(f"No item with id '{item_id}'.") from exc
    meta = rec.search.metadata
    source = meta.get(meta.position_of(item_id))
    results = serializers.scored(items, meta)
    return SimilarResponse(source=serializers.summary(source), total=len(results), results=results)


@router.get(
    "/{item_id}/recommendations", response_model=RecommendationsResponse, summary="Complete the Look"
)
async def recommendations(
    item_id: str = ItemId,
    per_group: int = Query(6, ge=1, le=24),
    rec: RecommendationService = Depends(get_recommendation),
):
    try:
        source, groups = await run_in_threadpool(rec.complete_the_look, item_id, per_group)
    except ItemNotFound as exc:
        raise not_found(f"No item with id '{item_id}'.") from exc
    meta = rec.search.metadata
    return RecommendationsResponse(
        source=serializers.summary(source),
        groups=[
            LookGroupOut(group=g.group, label=g.label, items=serializers.scored(g.items, meta))
            for g in groups
        ],
    )
