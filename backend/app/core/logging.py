"""Structured JSON logging (PRD §13.3): one line per request with latency and status."""

from __future__ import annotations

import json
import logging
import sys
import time


class JsonFormatter(logging.Formatter):
    def format(self, record: logging.LogRecord) -> str:
        payload = {
            "ts": time.strftime("%Y-%m-%dT%H:%M:%S", time.gmtime(record.created)),
            "level": record.levelname,
            "logger": record.name,
            "msg": record.getMessage(),
        }
        extra = getattr(record, "fields", None)
        if isinstance(extra, dict):
            payload.update(extra)
        if record.exc_info:
            payload["exc"] = self.formatException(record.exc_info)
        return json.dumps(payload, default=str)


def configure_logging(level: str = "INFO") -> None:
    handler = logging.StreamHandler(sys.stdout)
    handler.setFormatter(JsonFormatter())
    root = logging.getLogger()
    root.handlers[:] = [handler]
    root.setLevel(level)
    # Uvicorn's access log would duplicate our request log line.
    logging.getLogger("uvicorn.access").disabled = True


class RequestStats:
    """In-process counters surfaced by GET /health (no external metrics stack needed)."""

    def __init__(self) -> None:
        self.requests = 0
        self.errors = 0
        self.search_requests = 0
        self.search_latency_ms_total = 0.0

    def record(self, path: str, status: int, latency_ms: float) -> None:
        self.requests += 1
        if status >= 500:
            self.errors += 1
        if path.startswith("/search"):
            self.search_requests += 1
            self.search_latency_ms_total += latency_ms

    def snapshot(self) -> dict:
        avg = self.search_latency_ms_total / self.search_requests if self.search_requests else None
        return {
            "requests_total": self.requests,
            "server_errors_total": self.errors,
            "search_requests_total": self.search_requests,
            "avg_search_latency_ms": round(avg, 1) if avg is not None else None,
        }
