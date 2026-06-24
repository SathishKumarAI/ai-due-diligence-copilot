"""Observability (feature F09): JSON logging, request IDs, Prometheus metrics."""
from __future__ import annotations

import logging
import time
import uuid

import structlog
from prometheus_client import Counter, Histogram
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import Response

REQUESTS = Counter(
    "rag_requests_total", "Total HTTP requests", ["path", "method", "status"]
)
REQUEST_LATENCY = Histogram(
    "rag_request_latency_seconds", "Request latency in seconds", ["path", "method"]
)
ASK_LATENCY = Histogram(
    "rag_ask_stage_seconds", "RAG stage latency in seconds", ["stage"]
)
CACHE_HITS = Counter("rag_cache_hits_total", "Answer cache hits")


def configure_logging() -> None:
    structlog.configure(
        processors=[
            structlog.contextvars.merge_contextvars,
            structlog.processors.add_log_level,
            structlog.processors.TimeStamper(fmt="iso"),
            structlog.processors.JSONRenderer(),
        ],
        wrapper_class=structlog.make_filtering_bound_logger(logging.INFO),
    )


log = structlog.get_logger()


class RequestContextMiddleware(BaseHTTPMiddleware):
    """Attach a request id, log each request, and record metrics."""

    async def dispatch(self, request: Request, call_next) -> Response:
        request_id = request.headers.get("x-request-id", uuid.uuid4().hex)
        structlog.contextvars.bind_contextvars(request_id=request_id)
        start = time.perf_counter()
        path = request.url.path
        try:
            response = await call_next(request)
            status = response.status_code
        except Exception:
            REQUESTS.labels(path, request.method, 500).inc()
            log.exception("request_failed", path=path, method=request.method)
            structlog.contextvars.clear_contextvars()
            raise
        elapsed = time.perf_counter() - start
        REQUESTS.labels(path, request.method, status).inc()
        REQUEST_LATENCY.labels(path, request.method).observe(elapsed)
        response.headers["x-request-id"] = request_id
        log.info(
            "request",
            path=path,
            method=request.method,
            status=status,
            duration_ms=round(elapsed * 1000, 1),
        )
        structlog.contextvars.clear_contextvars()
        return response
