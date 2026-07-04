"""Pipeline trace / introspection (feature F23) — the "see how RAG works" layer.

Produces a structured record of every stage of an answer so the UI (and the docs)
can show a viewer exactly what happened:

    question ─► condense ─► tokenize ─► retrieve (+scores) ─► prompt ─► answer

This module is intentionally free of any dependency on ``rag.py`` (the engine imports
*this*, never the reverse) so there is no import cycle. It only knows about primitives:
Documents, the lexical tokenizer, and score maps handed to it by the engine.

Nothing here calls a model — it observes and formats data the engine already computed,
plus a best-effort dense-score probe of the vector store.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from langchain_core.documents import Document
from langchain_core.vectorstores import VectorStore

from app.retrieval import _doc_key, _tokenize

_SNIPPET_LEN = 280


@dataclass
class TokenizationTrace:
    """How the query text becomes tokens (the lexical/BM25 view of tokenization)."""

    text: str
    char_count: int
    word_count: int
    tokens: list[str]
    token_count: int
    tokenizer: str = "lexical BM25 (regex word+number tokens)"
    note: str = (
        "Dense embeddings use the model's subword tokenizer; shown here is the lexical "
        "tokenizer that drives the BM25 retrieval arm."
    )


@dataclass
class RetrievedChunkTrace:
    """One retrieved chunk as shown in the inspector."""

    rank: int
    source: str
    page: int | None
    extraction_method: str
    chars: int
    # Chroma's vector score is an L2 *distance*: SMALLER = more similar. Named
    # dense_score for the API, but interpret lower as closer (the UI bars do).
    dense_score: float | None
    snippet: str


@dataclass
class PipelineTrace:
    """Full end-to-end trace of a single answer."""

    original_question: str
    condensed_query: str
    condensed: bool
    tokenization: TokenizationTrace
    retrieval_mode: str
    rerank_enabled: bool
    retrieved: list[RetrievedChunkTrace] = field(default_factory=list)
    context_char_len: int = 0
    system_prompt: str = ""
    user_prompt: str = ""
    answer: str = ""
    timings_ms: dict[str, float] = field(default_factory=dict)


def tokenize_trace(text: str) -> TokenizationTrace:
    """Build the tokenization view for a query string."""
    tokens = _tokenize(text)
    return TokenizationTrace(
        text=text,
        char_count=len(text),
        word_count=len(text.split()),
        tokens=tokens,
        token_count=len(tokens),
    )


def dense_scores(vectorstore: VectorStore, query: str, k: int) -> dict[tuple, float]:
    """Best-effort map of chunk-key -> dense vector **distance** (lower = closer).

    Uses the store's scored search when available (Chroma returns an L2 distance).
    Returns an empty map for stores/fakes that don't, so the trace degrades gracefully.
    """
    try:
        pairs = vectorstore.similarity_search_with_score(query, k=k)
    except Exception:  # noqa: BLE001 - fake store or unsupported: no scores
        return {}
    return {_doc_key(doc): float(score) for doc, score in pairs}


def chunk_traces(
    docs: list[Document], score_map: dict[tuple, float]
) -> list[RetrievedChunkTrace]:
    """Turn the final ranked docs into inspector rows, attaching dense scores."""
    out: list[RetrievedChunkTrace] = []
    for i, d in enumerate(docs, start=1):
        text = " ".join(d.page_content.split())
        snippet = text[:_SNIPPET_LEN] + ("…" if len(text) > _SNIPPET_LEN else "")
        out.append(
            RetrievedChunkTrace(
                rank=i,
                source=d.metadata.get("source", "unknown"),
                page=d.metadata.get("page"),
                extraction_method=d.metadata.get("extraction_method", "text"),
                chars=len(d.page_content),
                dense_score=score_map.get(_doc_key(d)),
                snippet=snippet,
            )
        )
    return out
