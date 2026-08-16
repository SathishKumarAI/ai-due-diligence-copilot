"""Regression tests for the F07 caches (``app/cache.py``).

``wrap_embeddings`` had no coverage at all, which is how a namespace that could never
be written to disk shipped as the default for every ingest in all three repos.
"""

from __future__ import annotations

import re
from pathlib import Path

from app.cache import embedding_namespace
from app.config import Settings

# Copied from langchain.storage.file_system.LocalFileStore._get_full_path: every key
# it is asked to store must match this or it raises InvalidKeyException.
LOCAL_FILE_STORE_KEY = re.compile(r"^[a-zA-Z0-9_.\-/]+$")


def test_embedding_namespace_is_a_writable_local_file_store_key():
    # The failure this catches: "ollama:BAAI/bge-small-en-v1.5:voyage-3.5" — the colons
    # are rejected outright, and the slash would nest a stray "BAAI/" directory.
    for provider in ("ollama", "claude"):
        namespace = embedding_namespace(Settings(provider=provider))
        key = namespace + "ee0960b8-396a-5bb4-9edf-a776e9d398fb"  # a real hashed key
        assert LOCAL_FILE_STORE_KEY.match(key), f"unwritable key for {provider}: {key!r}"
        assert "/" not in namespace


def test_embedding_namespace_separates_providers():
    # A vector embedded by bge-small must never be served to a Voyage-backed engine.
    ollama = embedding_namespace(Settings(provider="ollama"))
    claude = embedding_namespace(Settings(provider="claude"))
    assert ollama != claude


def test_embedding_namespace_ignores_the_idle_provider_model():
    # Changing the Voyage model must not invalidate the local Ollama cache.
    before = embedding_namespace(Settings(provider="ollama"))
    after = embedding_namespace(Settings(provider="ollama", voyage_model="voyage-9-turbo"))
    assert before == after


# --- answer cache identity (the poisoning bug) -------------------------------------


def _cache(fingerprint: str = "", **overrides):
    from app.cache import AnswerCache

    return AnswerCache(Settings(**overrides), corpus_fingerprint=fingerprint)


def test_answers_do_not_survive_a_corpus_change():
    # The failure this catches: re-chunking took the index from 4 chunks to 11, which
    # changes every answer the system would give, while provider/question/top_k stayed
    # identical — so the stale answer was served indefinitely.
    before = _cache("due_diligence:4")
    after = _cache("due_diligence:11")
    assert before._key("What is the ARR?", 5) != after._key("What is the ARR?", 5)


def test_answers_do_not_cross_models():
    # Two runs of "ollama" against different models are not interchangeable answers.
    a = _cache("c:1", ollama_llm_model="llama3.1:8b")
    b = _cache("c:1", ollama_llm_model="qwen3-vl:8b")
    assert a._key("q", 5) != b._key("q", 5)


def test_identical_context_still_hits():
    a = _cache("c:1")
    b = _cache("c:1")
    assert a._key("What is the ARR?", 5) == b._key("what is the arr?  ", 5)


def test_tests_never_write_to_the_real_cache_dir(tmp_path):
    # Guards the autouse isolation fixture in conftest.py: if someone removes it, this
    # fails rather than silently poisoning .cache/answers again.
    from app.config import settings

    assert tmp_path.name in str(settings.cache_dir) or "cache" in str(settings.cache_dir)
    assert settings.cache_dir != Path(__file__).resolve().parent.parent / ".cache"
