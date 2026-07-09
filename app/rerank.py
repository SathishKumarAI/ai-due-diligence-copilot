"""Cross-encoder re-ranking (feature F17).

Retrieval (dense or hybrid) gives an approximate ordering. A cross-encoder reads
the (question, chunk) pair jointly and re-scores far more precisely, surfacing the
genuinely-answering passage into the top few the LLM sees.

The engine depends on the ``Reranker`` protocol, so the real cross-encoder is only
loaded when enabled and tests inject a deterministic fake (no model download).
"""

from __future__ import annotations

from typing import Protocol

from langchain_core.documents import Document


class Reranker(Protocol):
    def rerank(self, query: str, docs: list[Document], top_n: int) -> list[Document]: ...


class NoOpReranker:
    """Pass-through: keep retrieval order, just trim to ``top_n`` (F17 disabled path)."""

    def rerank(self, query: str, docs: list[Document], top_n: int) -> list[Document]:
        return docs[:top_n]


class CrossEncoderReranker:
    """Re-score with a sentence-transformers CrossEncoder. Model loaded lazily."""

    def __init__(self, model_name: str, device: str = "auto") -> None:
        self.model_name = model_name
        self.device = device
        self._model = None

    def _ensure_model(self):  # noqa: ANN202
        if self._model is None:
            from sentence_transformers import CrossEncoder

            from app.device import resolve_device

            # device: "auto" picks cuda -> mps -> cpu (see app/device.py / RERANK_DEVICE).
            self._model = CrossEncoder(self.model_name, device=resolve_device(self.device))
        return self._model

    def rerank(self, query: str, docs: list[Document], top_n: int) -> list[Document]:
        if not docs:
            return []
        model = self._ensure_model()
        scores = model.predict([(query, d.page_content) for d in docs])
        ranked = sorted(zip(docs, scores, strict=False), key=lambda ds: ds[1], reverse=True)
        return [d for d, _ in ranked[:top_n]]


def build_reranker(settings) -> Reranker:  # noqa: ANN001
    """Real cross-encoder when enabled, otherwise the no-op (F17)."""
    if settings.rerank_enabled:
        return CrossEncoderReranker(settings.rerank_model, settings.rerank_device)
    return NoOpReranker()
