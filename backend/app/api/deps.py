"""Shared FastAPI dependencies."""

from __future__ import annotations

from fastapi import Depends, Request

from ..container import Container
from ..core.security import COOKIE_NAME
from ..services.recommendation import RecommendationService
from ..services.search import SearchService
from .errors import service_unavailable, unauthorized


def get_container(request: Request) -> Container:
    return request.app.state.container


def require_session(request: Request, c: Container = Depends(get_container)) -> str | None:
    """No-op unless AUTH_ENABLED; then a valid signed session cookie is required."""
    if not c.settings.auth_enabled:
        return None
    user = c.signer.verify(request.cookies.get(COOKIE_NAME))
    if user is None:
        raise unauthorized()
    return user


def get_search(c: Container = Depends(get_container)) -> SearchService:
    if c.search is None:
        raise service_unavailable()
    return c.search


def get_recommendation(c: Container = Depends(get_container)) -> RecommendationService:
    if c.recommendation is None:
        raise service_unavailable()
    return c.recommendation
