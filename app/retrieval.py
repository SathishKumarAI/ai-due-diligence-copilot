"""Retrieval strategies (feature F16): dense, lexical (BM25), and hybrid fusion.

The RAG engine depends on the small ``Retriever`` protocol below, never on a
concrete vector store, so retrieval can be swapped (dense ↔ hybrid) by config and
faked in tests. BM25 is implemented in-process with no third-party dependency, so
the lexical arm stays offline and CI-friendly.
"""

from __future__ import annotations

import math
import re
from collections import Counter
from typing import Protocol

from langchain_core.documents import Document
from langchain_core.vectorstores import VectorStore

_TOKEN_RE = re.compile(r"[a-z0-9]+(?:[.,%$][a-z0-9]+)*")


def _tokenize(text: str) -> list[str]:
    """Lowercase word/number tokens; keeps figures like ``12.4`` and ``40%`` whole."""
    return _TOKEN_RE.findall(text.lower())


class Retriever(Protocol):
    def retrieve(self, query: str, k: int) -> list[Document]: ...


class DenseRetriever:
    """Semantic retrieval via the vector store (the F02 behaviour)."""

    def __init__(self, vectorstore: VectorStore) -> None:
        self.vectorstore = vectorstore

    def retrieve(self, query: str, k: int) -> list[Document]:
        return self.vectorstore.similarity_search(query, k=k)


class BM25Index:
    """Classic Okapi BM25 over a fixed list of documents. Dependency-free."""

    def __init__(self, docs: list[Document], *, k1: float = 1.5, b: float = 0.75) -> None:
        self.docs = docs
        self.k1 = k1
        self.b = b
        self._corpus = [_tokenize(d.page_content) for d in docs]
        self._doc_len = [len(toks) for toks in self._corpus]
        self._avg_len = (sum(self._doc_len) / len(self._corpus)) if self._corpus else 0.0
        self._freqs = [Counter(toks) for toks in self._corpus]
        n = len(self._corpus)
        df: Counter[str] = Counter()
        for toks in self._corpus:
            df.update(set(toks))
        # BM25+ idf, floored at 0 so common terms never push scores negative.
        self._idf = {
            term: max(0.0, math.log((n - freq + 0.5) / (freq + 0.5) + 1.0))
            for term, freq in df.items()
        }

    def search(self, query: str, k: int) -> list[Document]:
        if not self.docs:
            return []
        q_terms = _tokenize(query)
        scores: list[tuple[float, int]] = []
        for i, freqs in enumerate(self._freqs):
            score = 0.0
            for term in q_terms:
                tf = freqs.get(term, 0)
                if tf == 0:
                    continue
                idf = self._idf.get(term, 0.0)
                denom = tf + self.k1 * (
                    1 - self.b + self.b * (self._doc_len[i] / (self._avg_len or 1.0))
                )
                score += idf * (tf * (self.k1 + 1)) / denom
            if score > 0:
                scores.append((score, i))
        scores.sort(key=lambda s: s[0], reverse=True)
        return [self.docs[i] for _, i in scores[:k]]


def _doc_key(d: Document) -> tuple:
    """Stable identity for fusion/dedup: source + page + content."""
    return (d.metadata.get("source"), d.metadata.get("page"), d.page_content)


def reciprocal_rank_fusion(
    rankings: list[list[Document]], *, k: int, rrf_k: int = 60
) -> list[Document]:
    """Fuse several ranked lists into one via Reciprocal Rank Fusion.

    score(d) = Σ 1 / (rrf_k + rank_i(d)), summed across the lists d appears in.
    """
    scores: dict[tuple, float] = {}
    seen: dict[tuple, Document] = {}
    for ranking in rankings:
        for rank, doc in enumerate(ranking):
            key = _doc_key(doc)
            scores[key] = scores.get(key, 0.0) + 1.0 / (rrf_k + rank)
            seen.setdefault(key, doc)
    ordered = sorted(scores.items(), key=lambda kv: kv[1], reverse=True)
    return [seen[key] for key, _ in ordered[:k]]


class HybridRetriever:
    """Dense + BM25, fused with RRF (feature F16)."""

    def __init__(
        self,
        vectorstore: VectorStore,
        bm25: BM25Index,
        *,
        fetch_k: int = 20,
        rrf_k: int = 60,
    ) -> None:
        self.dense = DenseRetriever(vectorstore)
        self.bm25 = bm25
        self.fetch_k = fetch_k
        self.rrf_k = rrf_k

    def retrieve(self, query: str, k: int) -> list[Document]:
        dense_hits = self.dense.retrieve(query, self.fetch_k)
        lexical_hits = self.bm25.search(query, self.fetch_k)
        return reciprocal_rank_fusion([dense_hits, lexical_hits], k=k, rrf_k=self.rrf_k)


def all_documents(vectorstore: VectorStore) -> list[Document]:
    """Read every stored chunk out of a Chroma collection (to build BM25)."""
    try:
        data = vectorstore._collection.get(include=["documents", "metadatas"])  # type: ignore[attr-defined]
    except Exception:  # noqa: BLE001 - non-Chroma store or empty index
        return []
    texts = data.get("documents") or []
    metas = data.get("metadatas") or []
    return [
        Document(page_content=t or "", metadata=(m or {}))
        for t, m in zip(texts, metas, strict=False)
    ]


def build_retriever(vectorstore: VectorStore, settings) -> Retriever:  # noqa: ANN001
    """Pick the retriever for the configured mode (F16)."""
    if settings.retrieval_mode == "hybrid":
        bm25 = BM25Index(all_documents(vectorstore))
        return HybridRetriever(
            vectorstore, bm25, fetch_k=settings.retrieve_fetch_k, rrf_k=settings.rrf_k
        )
    return DenseRetriever(vectorstore)
