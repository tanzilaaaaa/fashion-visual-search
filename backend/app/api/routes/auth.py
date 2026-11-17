"""Optional basic session login (Could Have, PRD §11.1)."""

from __future__ import annotations

from fastapi import APIRouter, Depends, Request, Response

from ...container import Container
from ...core.security import COOKIE_NAME, credentials_match
from ...schemas.api import LoginRequest, SessionResponse
from ..deps import get_container
from ..errors import APIError
from ..limiter import limiter

router = APIRouter(prefix="/auth", tags=["auth"])


def _set_cookie(response: Response, c: Container, value: str, max_age: int) -> None:
    response.set_cookie(
        COOKIE_NAME, value, max_age=max_age, httponly=True,
        secure=c.settings.cookie_secure,
        # Frontend (Vercel) and API live on different sites in production.
        samesite="none" if c.settings.cookie_secure else "lax",
    )


@router.post("/login", response_model=SessionResponse)
@limiter.limit("10/minute")
def login(request: Request, body: LoginRequest, response: Response, c: Container = Depends(get_container)):
    if not c.settings.auth_enabled:
        return SessionResponse(authenticated=True, username=None, auth_enabled=False)
    if not credentials_match(body.username, body.password, c.settings.demo_username, c.settings.demo_password):
        raise APIError(401, "invalid_credentials", "Incorrect username or password.")
    _set_cookie(response, c, c.signer.issue(body.username), c.settings.session_max_age_s)
    return SessionResponse(authenticated=True, username=body.username, auth_enabled=True)


@router.post("/logout", response_model=SessionResponse)
def logout(response: Response, c: Container = Depends(get_container)):
    _set_cookie(response, c, "", 0)
    return SessionResponse(authenticated=False, auth_enabled=c.settings.auth_enabled)


@router.get("/me", response_model=SessionResponse)
def me(request: Request, c: Container = Depends(get_container)):
    if not c.settings.auth_enabled:
        return SessionResponse(authenticated=True, auth_enabled=False)
    user = c.signer.verify(request.cookies.get(COOKIE_NAME))
    return SessionResponse(authenticated=user is not None, username=user, auth_enabled=True)
