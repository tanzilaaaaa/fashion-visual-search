"""Error contract (PRD §8.1): consistent JSON body, safe messages, no internal paths."""

from __future__ import annotations

import logging

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from slowapi.errors import RateLimitExceeded
from starlette.exceptions import HTTPException as StarletteHTTPException

log = logging.getLogger(__name__)


class APIError(Exception):
    def __init__(self, status_code: int, code: str, message: str):
        super().__init__(message)
        self.status_code = status_code
        self.code = code
        self.message = message


def bad_request(message: str, code: str = "bad_request") -> APIError:
    return APIError(400, code, message)


def not_found(message: str) -> APIError:
    return APIError(404, "not_found", message)


def payload_too_large(message: str) -> APIError:
    return APIError(413, "payload_too_large", message)


def unauthorized(message: str = "Please sign in to continue.") -> APIError:
    return APIError(401, "unauthorized", message)


def service_unavailable(message: str = "The search index is still loading. Try again shortly.") -> APIError:
    return APIError(503, "not_ready", message)


def _body(code: str, message: str) -> dict:
    return {"error": {"code": code, "message": message}}


def register_error_handlers(app: FastAPI) -> None:
    @app.exception_handler(APIError)
    async def _api_error(_: Request, exc: APIError):
        return JSONResponse(status_code=exc.status_code, content=_body(exc.code, exc.message))

    @app.exception_handler(RequestValidationError)
    async def _validation(_: Request, exc: RequestValidationError):
        parts = []
        for err in exc.errors()[:5]:
            loc = ".".join(str(p) for p in err.get("loc", []) if p not in ("body", "query", "path"))
            parts.append(f"{loc or 'request'}: {err.get('msg', 'invalid value')}")
        return JSONResponse(status_code=422, content=_body("validation_error", "; ".join(parts)))

    @app.exception_handler(StarletteHTTPException)
    async def _http(_: Request, exc: StarletteHTTPException):
        code = {404: "not_found", 405: "method_not_allowed"}.get(exc.status_code, "http_error")
        message = exc.detail if isinstance(exc.detail, str) else "Request failed."
        return JSONResponse(status_code=exc.status_code, content=_body(code, message))

    @app.exception_handler(RateLimitExceeded)
    async def _rate(_: Request, exc: RateLimitExceeded):
        return JSONResponse(
            status_code=429,
            content=_body("rate_limited", "Too many requests — please slow down and retry in a moment."),
        )

    @app.exception_handler(Exception)
    async def _unhandled(request: Request, exc: Exception):
        log.exception("unhandled error", extra={"fields": {"path": request.url.path}})
        return JSONResponse(
            status_code=500,
            content=_body("internal_error", "Something went wrong on our side. Please try again."),
        )
