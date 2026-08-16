"""Regression tests for the F07 caches (``app/cache.py``).

``wrap_embeddings`` had no coverage at all, which is how a namespace that could never
be written to disk shipped as the default for every ingest in all three repos.
"""

from __future__ import annotations

import re

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
