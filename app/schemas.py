"""Pydantic request/response models for the API (feature F05)."""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field


class Turn(BaseModel):
    """One prior conversation exchange supplied by the client (feature F19)."""

    role: Literal["user", "assistant"]
    content: str = Field(..., min_length=1)


class AskRequest(BaseModel):
    question: str = Field(..., min_length=3, examples=["What are the main risks?"])
    top_k: int | None = Field(None, ge=1, le=20)
    history: list[Turn] = Field(
        default_factory=list,
        description="Prior turns, oldest first, for multi-turn follow-ups (F19).",
    )
    explain: bool = Field(
        False,
        description="If true, include a full pipeline trace in the response (F23).",
    )


class Citation(BaseModel):
    marker: int = Field(..., description="The [n] marker referenced in the answer")
    source: str = Field(..., description="Source filename")
    page: int | None = Field(None, description="Page number, if known")
    snippet: str = Field(..., description="The retrieved text the answer drew on")


class TokenizationTraceModel(BaseModel):
    text: str
    char_count: int
    word_count: int
    tokens: list[str]
    token_count: int
    tokenizer: str
    note: str


class RetrievedChunkTraceModel(BaseModel):
    rank: int
    source: str
    page: int | None
    extraction_method: str
    chars: int
    dense_score: float | None
    snippet: str


class PipelineTraceModel(BaseModel):
    """Full introspection trace of one answer (feature F23)."""

    original_question: str
    condensed_query: str
    condensed: bool
    tokenization: TokenizationTraceModel
    retrieval_mode: str
    rerank_enabled: bool
    retrieved: list[RetrievedChunkTraceModel]
    context_char_len: int
    system_prompt: str
    user_prompt: str
    answer: str
    timings_ms: dict[str, float] = Field(default_factory=dict)


class AskResponse(BaseModel):
    question: str
    answer: str
    citations: list[Citation]
    provider: str
    cached: bool = False
    timings_ms: dict[str, float] = Field(default_factory=dict)
    trace: PipelineTraceModel | None = Field(
        None, description="Pipeline trace, present only when explain=true (F23)."
    )


class IngestResponse(BaseModel):
    documents: int
    chunks: int
    collection: str


class SourceItem(BaseModel):
    source: str
    chunks: int


class SourcesResponse(BaseModel):
    sources: list[SourceItem]
    total_chunks: int


class UploadResponse(BaseModel):
    filename: str
    chunks_added: int
    collection: str


class FeedbackRequest(BaseModel):
    question: str = Field(..., min_length=1)
    answer: str = Field(..., min_length=1)
    rating: Literal["up", "down"]
    comment: str | None = Field(None, max_length=2000)


class FeedbackResponse(BaseModel):
    ok: bool
    up: int
    down: int
    total: int


class HealthResponse(BaseModel):
    status: str
    app: str
    version: str
    provider: str


class ReadyResponse(BaseModel):
    ready: bool
    indexed_chunks: int
