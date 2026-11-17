"""Rate limiting for the search endpoints (PRD §11.2)."""

from slowapi import Limiter
from slowapi.util import get_remote_address

limiter = Limiter(key_func=get_remote_address, headers_enabled=False)
_search_limit = {"value": "60/minute"}


def configure_limits(search_limit: str, enabled: bool) -> None:
    _search_limit["value"] = search_limit
    limiter.enabled = enabled
    limiter.reset()


def search_limit() -> str:
    return _search_limit["value"]
