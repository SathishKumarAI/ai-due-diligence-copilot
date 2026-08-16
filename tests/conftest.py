"""Offline test fixtures: deterministic fake embeddings + a fake chat model.

These let the whole RAG path run in CI with no model downloads and no network —
the provider seam (Embeddings / BaseChatModel) is exactly what we substitute.
"""

from __future__ import annotations

import hashlib

import pytest
from langchain_core.documents import Document
from langchain_core.embeddings import Embeddings
from langchain_core.messages import AIMessage, AIMessageChunk

_DIM = 64


class DeterministicFakeEmbeddings(Embeddings):
    """Hashing bag-of-words embedding — deterministic, offline, and good enough
    for similarity ranking in tests (shared words → higher similarity)."""

    def _embed(self, text: str) -> list[float]:
        vec = [0.0] * _DIM
        for word in text.lower().split():
            h = int(hashlib.md5(word.encode()).hexdigest(), 16) % _DIM
            vec[h] += 1.0
        norm = sum(v * v for v in vec) ** 0.5 or 1.0
        return [v / norm for v in vec]

    def embed_documents(self, texts: list[str]) -> list[list[float]]:
        return [self._embed(t) for t in texts]

    def embed_query(self, text: str) -> list[float]:
        return self._embed(text)


class FakeChat:
    """Duck-typed chat model: returns a fixed grounded answer citing [1]."""

    def __init__(self, reply: str = "Based on the passages, the answer is grounded [1].") -> None:
        self.reply = reply

    def invoke(self, messages):  # noqa: ANN001
        return AIMessage(content=self.reply)

    def stream(self, messages):  # noqa: ANN001
        for token in self.reply.split(" "):
            yield AIMessageChunk(content=token + " ")


@pytest.fixture
def sample_docs() -> list[Document]:
    return [
        Document(
            page_content="ARR is 12.4 million dollars up 39 percent year over year",
            metadata={"source": "pitch.md", "page": None},
        ),
        Document(
            page_content="One customer is 22 percent of ARR a concentration risk",
            metadata={"source": "risk.md", "page": None},
        ),
        Document(
            page_content="Post money valuation is 220 million on a 40 million raise",
            metadata={"source": "term_sheet.md", "page": None},
        ),
    ]


@pytest.fixture
def fake_store(sample_docs):
    from langchain_chroma import Chroma

    return Chroma.from_documents(
        sample_docs,
        embedding=DeterministicFakeEmbeddings(),
        collection_name="test_collection",
    )


@pytest.fixture
def fake_engine(fake_store):
    from app.rag import RagEngine

    return RagEngine(fake_store, FakeChat(), top_k=3, provider="fake")


@pytest.fixture
def client(monkeypatch, fake_engine):
    """TestClient wired to the fake engine, shared by every API-level test module.

    Stops the real engine being built in lifespan, which would download an embedding
    model and make the suite neither offline nor fast.
    """
    from fastapi.testclient import TestClient

    import app.main as main

    monkeypatch.setattr(main, "build_engine", lambda: fake_engine)
    main.app.dependency_overrides[main.get_engine] = lambda: fake_engine
    with TestClient(main.app) as c:
        yield c
    main.app.dependency_overrides.clear()


@pytest.fixture(autouse=True)
def isolate_caches(tmp_path, monkeypatch):
    """Never let the test suite touch the real .cache directory.

    It used to. The offline tests wrote fixture answers into the same diskcache the
    running app reads, and because the key was built from settings.provider ("ollama")
    while the answer came from a FakeChat engine, the app then served
    "Based on the passages, the answer is grounded [1]." to a real question. Autouse so
    no future test can opt out of the isolation by forgetting to ask for it.
    """
    from app.config import settings

    monkeypatch.setattr(settings, "cache_dir", tmp_path / "cache")
