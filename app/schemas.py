"""Pydantic request/response models for the API (feature F05)."""
from __future__ import annotations

from pydantic import BaseModel, Field


class AskRequest(BaseModel):
    question: str = Field(..., min_length=3, examples=["What are the main risks?"])
    top_k: int | None = Field(None, ge=1, le=20)


class Citation(BaseModel):
    marker: int = Field(..., description="The [n] marker referenced in the answer")
    source: str = Field(..., description="Source filename")
    page: int | None = Field(None, description="Page number, if known")
    snippet: str = Field(..., description="The retrieved text the answer drew on")


class AskResponse(BaseModel):
    question: str
    answer: str
    citations: list[Citation]
    provider: str
    cached: bool = False
    timings_ms: dict[str, float] = Field(default_factory=dict)


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


class HealthResponse(BaseModel):
    status: str
    app: str
    version: str
    provider: str


class ReadyResponse(BaseModel):
    ready: bool
    indexed_chunks: int
