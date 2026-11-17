"""FastAPI application factory."""

from __future__ import annotations

import logging
import time
import uuid
from collections.abc import Callable
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.middleware.gzip import GZipMiddleware
from slowapi.middleware import SlowAPIMiddleware

from . import __version__
from .api.errors import register_error_handlers
from .api.limiter import configure_limits, limiter
from .api.routes import auth, items, meta, search
from .container import Container, build_container
from .core.config import Settings, get_settings
from .core.logging import configure_logging

log = logging.getLogger("app")

ContainerFactory = Callable[[Settings], Container]


def create_app(settings: Settings | None = None, container_factory: ContainerFactory | None = None) -> FastAPI:
    settings = settings or get_settings()
    factory = container_factory or build_container

    @asynccontextmanager
    async def lifespan(app: FastAPI):
        # Load-only startup: the index, metadata and CLIP weights are packaged
        # artifacts — nothing is rebuilt here.
        app.state.container = factory(settings)
        yield

    app = FastAPI(
        title=settings.app_name,
        version=__version__,
        description=(
            "Multimodal fashion search over DeepFashion2 using CLIP ViT-B/32 embeddings and a FAISS "
            "index: text search, image search, Find Similar and Complete the Look."
        ),
        lifespan=lifespan,
    )

    configure_limits(settings.rate_limit, settings.rate_limit_enabled)
    app.state.limiter = limiter
    app.add_middleware(SlowAPIMiddleware)
    app.add_middleware(GZipMiddleware, minimum_size=1024)
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.allowed_origins,
        allow_credentials=True,
        allow_methods=["GET", "POST"],
        allow_headers=["Content-Type"],
        max_age=600,
    )

    @app.middleware("http")
    async def request_log(request: Request, call_next):
        request_id = request.headers.get("x-request-id") or uuid.uuid4().hex[:12]
        t0 = time.perf_counter()
        status = 500
        try:
            response = await call_next(request)
            status = response.status_code
        finally:
            latency_ms = (time.perf_counter() - t0) * 1000
            container = getattr(request.app.state, "container", None)
            if container is not None:
                container.stats.record(request.url.path, status, latency_ms)
            # Query text and uploads are deliberately not logged (PRD §11.3).
            log.info("request", extra={"fields": {
                "request_id": request_id, "method": request.method, "path": request.url.path,
                "status": status, "latency_ms": round(latency_ms, 1),
            }})
        response.headers["X-Request-ID"] = request_id
        response.headers["X-Content-Type-Options"] = "nosniff"
        return response

    register_error_handlers(app)
    for router in (search.router, items.router, meta.router, auth.router):
        app.include_router(router)

    @app.get("/", include_in_schema=False)
    def root():
        return {"name": settings.app_name, "version": __version__, "docs": "/docs", "health": "/health"}

    return app


def _default_app() -> FastAPI:
    configure_logging()
    return create_app()


app = _default_app()
