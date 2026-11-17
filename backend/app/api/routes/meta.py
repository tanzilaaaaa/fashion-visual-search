"""Filters vocabulary, image serving, health and evaluation report."""

from __future__ import annotations

from fastapi import APIRouter, Depends, Path
from fastapi.responses import FileResponse

from ...container import Container
from ...schemas.api import FiltersResponse, HealthResponse
from ..deps import get_container
from ..errors import not_found, service_unavailable

router = APIRouter(tags=["meta"])


@router.get("/health", response_model=HealthResponse, summary="Liveness + model/index status")
def health(c: Container = Depends(get_container)):
    return HealthResponse(
        status="ok" if c.ready else "degraded",
        model_loaded=c.embedding is not None,
        index_loaded=c.index is not None and c.metadata is not None,
        item_count=c.index.size if c.index else 0,
        model=c.embedding.model_name if c.embedding else None,
        startup_error=c.startup_error,
        stats=c.stats.snapshot(),
    )


@router.get("/filters", response_model=FiltersResponse, summary="Supported filter values")
def filters(c: Container = Depends(get_container)):
    if c.metadata is None:
        raise service_unavailable()
    return FiltersResponse(fields=c.metadata.vocabulary())


@router.get("/images/{item_id}", summary="Serve a garment thumbnail", response_class=FileResponse)
def image(
    item_id: str = Path(..., pattern=r"^[A-Za-z0-9_-]{1,64}$"),
    c: Container = Depends(get_container),
):
    # The id is validated by the pattern and checked against the catalogue, so a
    # request can never escape IMAGE_DIR.
    if c.metadata is None or c.metadata.position_of(item_id) is None:
        raise not_found("Image not found.")
    path = c.settings.resolved_image_dir / f"{item_id}.webp"
    if not path.is_file():
        raise not_found("Image not found.")
    return FileResponse(
        path, media_type="image/webp", headers={"Cache-Control": "public, max-age=604800, immutable"}
    )


@router.get("/evaluation", summary="Offline evaluation report and catalogue manifest")
def evaluation(c: Container = Depends(get_container)):
    if c.evaluation is None and c.manifest is None:
        raise not_found("No evaluation report has been generated for this index yet.")
    manifest = dict(c.manifest or {})
    manifest.pop("cleaning", None)
    return {"evaluation": c.evaluation, "manifest": manifest}
