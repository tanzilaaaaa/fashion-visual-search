"""Shared FastAPI dependencies."""

from __future__ import annotations

from fastapi import Depends, Request

from ..container import Container
from ..core.security import COOKIE_NAME
from ..services.recommendation import RecommendationService
from ..services.search import SearchService
from ..services.users import User
from .errors import service_unavailable, unauthorized


def get_container(request: Request) -> Container:
    return request.app.state.container


def current_user(request: Request, c: Container = Depends(get_container)) -> User | None:
    """The signed-in user, or ``None`` (also ``None`` when the account no longer exists)."""
    uid = c.signer.verify(request.cookies.get(COOKIE_NAME))
    return c.users.get(uid) if uid is not None else None


def require_session(c: Container = Depends(get_container), user: User | None = Depends(current_user)) -> User | None:
    """No-op unless AUTH_ENABLED; then a valid session for an existing account is required."""
    if not c.settings.auth_enabled:
        return user
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
