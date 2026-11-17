"""Accounts: register, sign in, sign out, current session (PRD §11.1)."""

from __future__ import annotations

from fastapi import APIRouter, Depends, Request, Response

from ...container import Container
from ...core.security import COOKIE_NAME
from ...schemas.api import LoginRequest, RegisterRequest, SessionResponse, UserOut
from ...services.users import EmailTaken, User, normalise_email, password_problem, valid_email
from ..deps import current_user, get_container
from ..errors import APIError, bad_request
from ..limiter import limiter

router = APIRouter(prefix="/auth", tags=["auth"])


def _set_cookie(response: Response, c: Container, value: str, max_age: int) -> None:
    # The frontend reaches the API through a same-origin /api proxy (Vite in dev,
    # a Vercel rewrite in production), so the cookie is first-party and Lax works
    # in every browser, including Safari with third-party cookies blocked.
    response.set_cookie(
        COOKIE_NAME, value, max_age=max_age, httponly=True, secure=c.settings.cookie_secure,
        samesite="lax", path="/",
    )


def _session(c: Container, user: User | None) -> SessionResponse:
    return SessionResponse(
        authenticated=user is not None or not c.settings.auth_enabled,
        auth_enabled=c.settings.auth_enabled,
        user=UserOut(id=user.id, name=user.name, email=user.email) if user else None,
    )


@router.post("/register", response_model=SessionResponse, status_code=201, summary="Create an account and sign in")
@limiter.limit("5/minute")
def register(request: Request, body: RegisterRequest, response: Response, c: Container = Depends(get_container)):
    name = " ".join(body.name.split())
    email = normalise_email(body.email)
    if not name:
        raise bad_request("Please enter your name.", "invalid_name")
    if not valid_email(email):
        raise bad_request("Please enter a valid email address.", "invalid_email")
    if problem := password_problem(body.password):
        raise bad_request(problem, "weak_password")
    try:
        user = c.users.create(name, email, body.password)
    except EmailTaken:
        raise APIError(409, "email_taken", "An account with this email already exists. Try signing in.") from None
    _set_cookie(response, c, c.signer.issue(user.id), c.settings.session_max_age_s)
    return _session(c, user)


@router.post("/login", response_model=SessionResponse, summary="Sign in with email and password")
@limiter.limit("10/minute")
def login(request: Request, body: LoginRequest, response: Response, c: Container = Depends(get_container)):
    user = c.users.authenticate(body.email, body.password)
    if user is None:
        raise APIError(401, "invalid_credentials", "Incorrect email or password.")
    _set_cookie(response, c, c.signer.issue(user.id), c.settings.session_max_age_s)
    return _session(c, user)


@router.post("/logout", response_model=SessionResponse, summary="Sign out")
def logout(response: Response, c: Container = Depends(get_container)):
    _set_cookie(response, c, "", 0)
    return SessionResponse(authenticated=not c.settings.auth_enabled, auth_enabled=c.settings.auth_enabled)


@router.get("/me", response_model=SessionResponse, summary="Current session")
def me(c: Container = Depends(get_container), user: User | None = Depends(current_user)):
    return _session(c, user)
