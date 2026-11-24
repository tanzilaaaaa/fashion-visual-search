"""POST /search/text and POST /search/image."""

from __future__ import annotations

import io
import json

from fastapi import APIRouter, Depends, File, Form, Request, UploadFile
from fastapi.concurrency import run_in_threadpool
from PIL import Image, UnidentifiedImageError
from pydantic import ValidationError

from ...container import Container
from ...schemas.api import Filters, Ranking, SearchResponse, TextSearchRequest
from ...services.metadata import UnknownFilterValue
from ...services.search import RankingWeights, SearchOutcome, SearchService
from ...services.users import User
from .. import serializers
from ..deps import current_user, get_container, get_search, require_session
from ..errors import APIError, bad_request, payload_too_large
from ..limiter import limiter, search_limit

router = APIRouter(prefix="/search", tags=["search"], dependencies=[Depends(require_session)])

ALLOWED_TYPES = {"image/jpeg", "image/png", "image/webp"}
# Magic numbers checked before decoding — the declared content type is client-controlled.
MAGIC = (b"\xff\xd8\xff", b"\x89PNG\r\n\x1a\n", b"RIFF")
Image.MAX_IMAGE_PIXELS = 40_000_000  # decompression-bomb guard


def _weights(c: Container, alpha: float | None, beta: float | None) -> RankingWeights:
    return RankingWeights(
        alpha=c.settings.rank_alpha if alpha is None else alpha,
        beta=c.settings.rank_beta if beta is None else beta,
    )


def _top_k(c: Container, top_k: int | None) -> int:
    return min(top_k or c.settings.top_k_default, c.settings.top_k_max)


def _response(mode: str, out: SearchOutcome, search: SearchService, query: str | None = None) -> SearchResponse:
    results = serializers.scored(out.items, search.metadata)
    return SearchResponse(
        mode=mode,
        query=query,
        total=len(results),
        results=results,
        applied_filters=out.filters,
        detected=out.detected.as_dict(),
        inferred=out.extras.get("inferred"),
        ranking=Ranking(
            alpha=out.weights.alpha,
            beta=out.weights.beta,
            attribute_signal_used=out.detected.has_attributes and out.weights.beta > 0,
        ),
        candidates_considered=out.candidates_considered,
        latency_ms=round(out.latency_ms, 1),
    )


@router.post("/text", response_model=SearchResponse, summary="Natural-language fashion search")
@limiter.limit(search_limit)
async def search_text(
    request: Request,
    body: TextSearchRequest,
    c: Container = Depends(get_container),
    search: SearchService = Depends(get_search),
    user: User | None = Depends(current_user),
):
    query = body.query.strip()
    if not query:
        raise bad_request("Please enter a description to search for.", "empty_query")
    if len(query) > c.settings.max_query_chars:
        raise bad_request(f"Query is too long (max {c.settings.max_query_chars} characters).", "query_too_long")
    try:
        out = await run_in_threadpool(
            search.search_text, query, _top_k(c, body.top_k), body.filters.as_dict(),
            _weights(c, body.alpha, body.beta),
        )
    except UnknownFilterValue as exc:
        raise bad_request(str(exc), "unsupported_filter") from exc
    if user is not None:
        # Synced search history: successful text queries follow the account across devices.
        await run_in_threadpool(c.profiles.record_search, user.id, query)
    return _response("text", out, search, query)


def _parse_filters(raw: str | None) -> dict[str, list[str]]:
    if not raw:
        return {}
    try:
        return Filters.model_validate(json.loads(raw)).as_dict()
    except (json.JSONDecodeError, ValidationError) as exc:
        raise bad_request("'filters' must be a JSON object like {\"category\": [\"skirt\"]}.",
                          "malformed_filters") from exc


async def _read_upload(request: Request, file: UploadFile, limit: int) -> bytes:
    if (file.content_type or "").lower() not in ALLOWED_TYPES:
        raise bad_request("Unsupported file type. Upload a JPEG, PNG or WebP image.", "unsupported_type")
    declared = request.headers.get("content-length")
    if declared and declared.isdigit() and int(declared) > limit + 64 * 1024:
        raise payload_too_large(f"Image is larger than {limit // (1024 * 1024)} MB.")
    data = bytearray()
    while chunk := await file.read(256 * 1024):
        data.extend(chunk)
        if len(data) > limit:
            raise payload_too_large(f"Image is larger than {limit // (1024 * 1024)} MB.")
    if not data:
        raise bad_request("The uploaded file is empty.", "empty_file")
    if not bytes(data[:12]).startswith(MAGIC) or (data[:4] == b"RIFF" and data[8:12] != b"WEBP"):
        raise bad_request("The file content is not a JPEG, PNG or WebP image.", "unsupported_type")
    return bytes(data)


def _decode(data: bytes) -> Image.Image:
    try:
        img = Image.open(io.BytesIO(data))
        img.load()
        return img.convert("RGB")
    except (UnidentifiedImageError, OSError, Image.DecompressionBombError) as exc:
        raise bad_request("The image could not be read. It may be corrupted.", "invalid_image") from exc


@router.post("/image", response_model=SearchResponse, summary="Image-to-fashion search")
@limiter.limit(search_limit)
async def search_image(
    request: Request,
    file: UploadFile | None = File(None, description="JPEG, PNG or WebP image"),
    top_k: int | None = Form(None, ge=1, le=100),
    filters: str | None = Form(None, description='JSON, e.g. {"category": ["skirt"]}'),
    alpha: float | None = Form(None, ge=0, le=1),
    beta: float | None = Form(None, ge=0, le=1),
    c: Container = Depends(get_container),
    search: SearchService = Depends(get_search),
):
    if file is None:
        raise bad_request("Please attach an image file.", "missing_file")
    data = await _read_upload(request, file, c.settings.max_upload_bytes)
    parsed_filters = _parse_filters(filters)
    image = await run_in_threadpool(_decode, data)
    try:
        out = await run_in_threadpool(
            search.search_image, image, _top_k(c, top_k), parsed_filters, _weights(c, alpha, beta)
        )
    except UnknownFilterValue as exc:
        raise bad_request(str(exc), "unsupported_filter") from exc
    finally:
        del data  # the upload is never persisted (PRD §11.3)
    return _response("image", out, search)


__all__ = ["router", "APIError"]
