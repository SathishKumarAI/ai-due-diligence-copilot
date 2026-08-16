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
import re
from typing import Any

from langchain.embeddings import CacheBackedEmbeddings
from langchain.storage import LocalFileStore
from langchain_core.embeddings import Embeddings

from app.config import Settings


def embedding_namespace(settings: Settings) -> str:
    """Filesystem-safe cache namespace for the *active* provider's embedding model.

    CacheBackedEmbeddings prefixes every key with this string and LocalFileStore turns
    the result into a path, validating it against ``^[a-zA-Z0-9_.\\-/]+$``. The obvious
    spelling -- "{provider}:{hf_model}:{voyage_model}" -- fails on the colons, so every
    ingest died with InvalidKeyException before writing a single vector. A "/" would
    have passed that check but silently nested a "BAAI/" directory, so it goes too.

    Only the active provider's model is included: switching providers must land in a
    different namespace, and the idle provider's model name has no business in the key.
    """
    model = settings.voyage_model if settings.provider == "claude" else settings.hf_embed_model
    return re.sub(r"[^A-Za-z0-9_.-]", "_", f"{settings.provider}-{model}") + "-"


def wrap_embeddings(embeddings: Embeddings, settings: Settings) -> Embeddings:
    """Return embeddings with a persistent cache in front, if enabled."""
    if not settings.cache_enabled:
        return embeddings
    store = LocalFileStore(str(settings.cache_dir / "embeddings"))
    return CacheBackedEmbeddings.from_bytes_store(
        embeddings, store, namespace=embedding_namespace(settings)
    )


class AnswerCache:
    """Tiny TTL cache for full answers. No-op when disabled.

    The key deliberately includes a *corpus fingerprint*. Without one the cache answers
    from a corpus that no longer exists: re-chunking or ingesting new documents changes
    every answer the system would give, while the key — provider, question, top_k — stays
    identical, so the old answer is served indefinitely.

    This is not hypothetical. Running the test suite once poisoned the live cache with
    fixture responses: the offline tests write to the same ``.cache`` directory, the key
    was built from ``settings.provider`` ("ollama") while the answer came from a fake
    engine, and the running app then served "Based on the passages, the answer is
    grounded [1]." to a real question. The fingerprint plus the model identity below make
    those keys disjoint; tests also get their own cache directory now.
    """

    def __init__(self, settings: Settings, corpus_fingerprint: str = "") -> None:
        self.enabled = settings.cache_enabled
        self.ttl = settings.cache_ttl_seconds
        self._cache: Any = None
        if self.enabled:
            from diskcache import Cache

            self._cache = Cache(str(settings.cache_dir / "answers"))
        self._provider = settings.provider
        # The generating model matters as much as the provider name: two runs of
        # "ollama" against different models are not interchangeable answers.
        self._model = (
            settings.anthropic_model if settings.provider == "claude" else settings.ollama_llm_model
        )
        self._fingerprint = corpus_fingerprint

    def _key(self, question: str, top_k: int) -> str:
        raw = json.dumps(
            [self._provider, self._model, self._fingerprint, question.strip().lower(), top_k]
        )
        return hashlib.sha256(raw.encode()).hexdigest()

    def get(self, question: str, top_k: int) -> dict | None:
        if not self.enabled:
            return None
        return self._cache.get(self._key(question, top_k))

    def set(self, question: str, top_k: int, value: dict) -> None:
        if not self.enabled:
            return
        self._cache.set(self._key(question, top_k), value, expire=self.ttl)
