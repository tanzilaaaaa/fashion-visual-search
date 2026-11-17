"""Wires the services together once at startup (model + index loaded into memory)."""

from __future__ import annotations

import json
import logging
import time
from dataclasses import dataclass, field

from .core.config import Settings
from .core.logging import RequestStats
from .core.security import SessionSigner
from .services.adapter import Adapter
from .services.embedding import ClipEncoder, EmbeddingService, Encoder
from .services.index import IndexService
from .services.metadata import MetadataService
from .services.recommendation import CompatibilityMap, RecommendationService
from .services.search import RankingWeights, SearchService
from .services.users import UserStore

log = logging.getLogger(__name__)


@dataclass
class Container:
    settings: Settings
    stats: RequestStats
    signer: SessionSigner
    users: UserStore
    embedding: EmbeddingService | None = None
    index: IndexService | None = None
    metadata: MetadataService | None = None
    search: SearchService | None = None
    recommendation: RecommendationService | None = None
    evaluation: dict | None = None
    manifest: dict | None = None
    startup_error: str | None = None
    load_seconds: dict = field(default_factory=dict)

    @property
    def ready(self) -> bool:
        return self.search is not None and self.recommendation is not None


def _read_json(path) -> dict | None:
    try:
        with open(path, encoding="utf-8") as fh:
            return json.load(fh)
    except (OSError, json.JSONDecodeError):
        return None


def build_container(settings: Settings, encoder: Encoder | None = None) -> Container:
    c = Container(
        settings=settings,
        stats=RequestStats(),
        signer=SessionSigner(settings.session_secret, settings.session_max_age_s),
        users=UserStore(settings.resolved_users_db_path),
    )
    artifacts = settings.resolved_index_path.parent
    c.manifest = _read_json(artifacts / "manifest.json")
    c.evaluation = _read_json(settings.resolved_evaluation_path)
    try:
        t = time.perf_counter()
        c.index = IndexService.load(settings.resolved_index_path)
        c.metadata = MetadataService.load(settings.resolved_metadata_path)
        c.load_seconds["index_and_metadata"] = round(time.perf_counter() - t, 2)

        # The index holds adapted vectors when the build was fine-tuned; query images must match.
        adapter_info = (c.manifest or {}).get("adapter")
        adapter = None
        if adapter_info:
            adapter_path = artifacts / adapter_info.get("file", "adapter.npz")
            if not adapter_path.exists():
                raise FileNotFoundError("manifest expects a fine-tuned adapter but adapter.npz is missing")
            adapter = Adapter.from_npz(adapter_path)
            if adapter.dim != c.index.dim:
                raise ValueError(f"adapter dim {adapter.dim} != index dim {c.index.dim}")
        text_index = None
        text_info = (c.manifest or {}).get("text_index")
        if text_info:
            text_index = IndexService.load(artifacts / text_info.get("file", "text_index.faiss"))

        if encoder is None and settings.load_model_on_startup:
            t = time.perf_counter()
            encoder = ClipEncoder(settings.model_name, settings.model_pretrained)
            c.load_seconds["model"] = round(time.perf_counter() - t, 2)
        if encoder is not None:
            if encoder.dim != c.index.dim:
                raise ValueError(f"encoder dim {encoder.dim} != index dim {c.index.dim}")
            c.embedding = EmbeddingService(encoder, adapter=adapter)
            c.search = SearchService(
                c.embedding, c.index, c.metadata,
                RankingWeights(settings.rank_alpha, settings.rank_beta),
                settings.candidate_multiplier,
                text_index=text_index,
            )
            c.recommendation = RecommendationService(
                c.search, CompatibilityMap.load(settings.compatibility_path)
            )
    except Exception as exc:  # noqa: BLE001 — surface via /health instead of crashing
        log.exception("startup failed")
        c.startup_error = type(exc).__name__
    log.info("container ready", extra={"fields": {"ready": c.ready, "load_seconds": c.load_seconds}})
    return c
