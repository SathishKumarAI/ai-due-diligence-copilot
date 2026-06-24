"""Auth + rate limiting (feature F08).

- API-key auth: enforced only when settings.api_key is set (so the default OSS
  setup runs key-free locally, but production can require X-API-Key).
- Rate limiting: in-memory token bucket per key (or client IP if no key).
"""
from __future__ import annotations

import time
from collections import defaultdict

from fastapi import Header, HTTPException, Request, status

from app.config import settings


async def require_api_key(x_api_key: str | None = Header(default=None)) -> None:
    if not settings.auth_required:
        return
    if x_api_key != settings.api_key:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Missing or invalid X-API-Key.",
        )


class TokenBucket:
    def __init__(self, rate_per_min: int) -> None:
        self.capacity = float(rate_per_min)
        self.refill_per_sec = rate_per_min / 60.0
        self._tokens: dict[str, float] = defaultdict(lambda: self.capacity)
        self._last: dict[str, float] = defaultdict(time.monotonic)

    def allow(self, key: str) -> bool:
        now = time.monotonic()
        elapsed = now - self._last[key]
        self._last[key] = now
        self._tokens[key] = min(
            self.capacity, self._tokens[key] + elapsed * self.refill_per_sec
        )
        if self._tokens[key] >= 1.0:
            self._tokens[key] -= 1.0
            return True
        return False


_bucket = TokenBucket(settings.rate_limit_per_min)


async def rate_limit(request: Request, x_api_key: str | None = Header(default=None)) -> None:
    key = x_api_key or (request.client.host if request.client else "anonymous")
    if not _bucket.allow(key):
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail="Rate limit exceeded. Slow down.",
        )
