"""Caching for embeddings and answers (feature F07).

Two layers:
  - embedding cache: wraps any Embeddings so repeated chunks aren't re-embedded.
  - answer cache: keyed by (provider, question, top_k); avoids re-running the LLM
    for an identical question while the corpus is unchanged.

Both are backed by diskcache so they survive restarts. Disabled cleanly when
settings.cache_enabled is False.
"""
from __future__ import annotations

import hashlib
import json
from typing import Any

from langchain.embeddings import CacheBackedEmbeddings
from langchain.storage import LocalFileStore
from langchain_core.embeddings import Embeddings

from app.config import Settings


def wrap_embeddings(embeddings: Embeddings, settings: Settings) -> Embeddings:
    """Return embeddings with a persistent cache in front, if enabled."""
    if not settings.cache_enabled:
        return embeddings
    store = LocalFileStore(str(settings.cache_dir / "embeddings"))
    namespace = f"{settings.provider}:{settings.hf_embed_model}:{settings.voyage_model}"
    return CacheBackedEmbeddings.from_bytes_store(
        embeddings, store, namespace=namespace
    )


class AnswerCache:
    """Tiny TTL cache for full answers. No-op when disabled."""

    def __init__(self, settings: Settings) -> None:
        self.enabled = settings.cache_enabled
        self.ttl = settings.cache_ttl_seconds
        self._cache: Any = None
        if self.enabled:
            from diskcache import Cache

            self._cache = Cache(str(settings.cache_dir / "answers"))
        self._provider = settings.provider

    def _key(self, question: str, top_k: int) -> str:
        raw = json.dumps([self._provider, question.strip().lower(), top_k])
        return hashlib.sha256(raw.encode()).hexdigest()

    def get(self, question: str, top_k: int) -> dict | None:
        if not self.enabled:
            return None
        return self._cache.get(self._key(question, top_k))

    def set(self, question: str, top_k: int, value: dict) -> None:
        if not self.enabled:
            return
        self._cache.set(self._key(question, top_k), value, expire=self.ttl)
