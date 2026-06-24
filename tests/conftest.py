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
        Document(page_content="ARR is 12.4 million dollars up 39 percent year over year",
                 metadata={"source": "pitch.md", "page": None}),
        Document(page_content="One customer is 22 percent of ARR a concentration risk",
                 metadata={"source": "risk.md", "page": None}),
        Document(page_content="Post money valuation is 220 million on a 40 million raise",
                 metadata={"source": "term_sheet.md", "page": None}),
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
