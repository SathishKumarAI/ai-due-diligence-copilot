"""FastAPI application (feature F05): /v1 routes, auth, metrics, streaming.

The RAG engine is built once at startup and stored on app.state, so requests are
cheap and tests can override the dependency with a fake engine.
"""

from __future__ import annotations

import json
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from dataclasses import asdict
from pathlib import Path

from fastapi import Depends, FastAPI, HTTPException, Query, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse, PlainTextResponse
from prometheus_client import CONTENT_TYPE_LATEST, generate_latest
from sse_starlette.sse import EventSourceResponse

from app import schemas
from app.cache import AnswerCache, wrap_embeddings
from app.config import settings
from app.feedback import feedback_summary, record_feedback
from app.observability import (
    ASK_LATENCY,
    CACHE_HITS,
    RequestContextMiddleware,
    configure_logging,
    log,
)
from app.providers import get_embeddings, get_llm
from app.rag import RagEngine, Turn
from app.rerank import build_reranker
from app.retrieval import build_retriever
from app.security import rate_limit, require_api_key


def build_engine() -> RagEngine:
    """Construct the production engine from the configured provider + index."""
    from app.ingest import load_index

    embeddings = wrap_embeddings(get_embeddings(settings), settings)
    store = load_index(settings, embeddings)
    llm = get_llm(settings)
    return RagEngine(
        store,
        llm,
        top_k=settings.top_k,
        provider=settings.active_llm_provider,
        retriever=build_retriever(store, settings),
        reranker=build_reranker(settings),
        fetch_k=settings.retrieve_fetch_k,
        history_max_turns=settings.history_max_turns,
        max_chunks_per_source=settings.max_chunks_per_source,
    )


def _to_turns(history: list[schemas.Turn]) -> list[Turn]:
    return [Turn(role=t.role, content=t.content) for t in history]


def _cache_question(question: str, history: list[schemas.Turn]) -> str:
    """Cache key fold-in: follow-ups must not collide with the same words asked cold."""
    if not history:
        return question
    tail = json.dumps([(t.role, t.content) for t in history], ensure_ascii=False)
    return f"{question}\x00{tail}"


def _count_chunks(engine: RagEngine | None) -> int | None:
    """Chunks in the live collection, or None when the handle can no longer answer.

    None is the signal that the process is holding a collection that has been replaced
    underneath it — see :func:`get_engine`.
    """
    if engine is None:
        return None
    try:
        return int(engine.vectorstore._collection.count())  # type: ignore[attr-defined]
    except Exception:  # noqa: BLE001 - non-Chroma store, or a handle whose collection is gone
        return None


def _corpus_fingerprint() -> str:
    """Identify the indexed corpus, so cached answers do not outlive it."""
    engine = getattr(app.state, "engine", None)
    if engine is None:
        return "no-index"
    count = _count_chunks(engine)
    if count is None:
        return "unknown"
    return f"{settings.active_collection_name}:{count}"


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    configure_logging()
    try:
        app.state.engine = build_engine()
        log.info(
            "engine_ready",
            llm_provider=settings.active_llm_provider,
            llm_model=settings.active_llm_model,
            embed_provider=settings.active_embed_provider,
            embed_model=settings.active_embed_model,
        )
    except Exception as exc:  # noqa: BLE001 - degrade gracefully if not yet ingested
        app.state.engine = None
        log.warning("engine_unavailable", error=str(exc))
    # Built after the engine so the cache key can carry a corpus fingerprint: an answer
    # cached against a 4-chunk index must not be served from an 11-chunk one. Chunk count
    # is coarse — it misses an edit that leaves the count unchanged — but it catches
    # ingest, upload and re-chunking, which is what actually changes answers.
    app.state.cache = AnswerCache(settings, corpus_fingerprint=_corpus_fingerprint())
    yield


app = FastAPI(title=settings.app_name, version=settings.app_version, lifespan=lifespan)
app.add_middleware(RequestContextMiddleware)
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins,
    allow_methods=["*"],
    allow_headers=["*"],
)


def get_engine() -> RagEngine:
    """The live engine, rebuilt in place if its collection was replaced underneath it.

    `python -m app.ingest` is the documented way to (re)build the index and it runs in a
    *separate process*. Doing that while the API serves used to break the running
    instance permanently: Chroma resets the collection, this process keeps a handle to
    the old one, and every subsequent request died with an opaque 500 — the UI reported
    "Could not load the trace. Is the backend running?" while the backend was running
    fine. Only a restart recovered it.

    Rebuilding on demand costs one collection count per request. Measured at 0.25 ms
    (2000 calls, local Chroma/SQLite, 11 chunks) against an /v1/ask that spends seconds
    in the LLM — the cost is not detectable, and it removes the failure class entirely.
    """
    engine = getattr(app.state, "engine", None)

    if engine is not None and _count_chunks(engine) is None:
        log.warning("engine_handle_stale", action="rebuilding")
        try:
            engine = build_engine()
        except Exception as exc:  # noqa: BLE001 - report why rather than 500 opaquely
            app.state.engine = None
            raise HTTPException(503, f"Index unavailable and could not be reloaded: {exc}") from exc
        app.state.engine = engine
        # The corpus changed, so the old cache is keyed to a corpus that no longer
        # exists. Rebuilding the cache re-derives the fingerprint and stops answers from
        # the previous index being served against the new one.
        app.state.cache = AnswerCache(settings, corpus_fingerprint=_corpus_fingerprint())
        log.info("engine_reloaded", chunks=_count_chunks(engine))

    if engine is None:
        raise HTTPException(503, "Index not built. Run `python -m app.ingest` first.")
    return engine


# --- health / readiness (unauthenticated) ---


@app.get("/health", response_model=schemas.HealthResponse, tags=["ops"])
def health() -> schemas.HealthResponse:
    return schemas.HealthResponse(
        status="ok",
        app=settings.app_name,
        version=settings.app_version,
        provider=settings.active_llm_provider,
        llm_model=settings.active_llm_model,
        embed_provider=settings.active_embed_provider,
        embed_model=settings.active_embed_model,
    )


@app.get("/ready", response_model=schemas.ReadyResponse, tags=["ops"])
def ready() -> schemas.ReadyResponse:
    engine = getattr(app.state, "engine", None)
    count = _count_chunks(engine)
    n = 0 if engine is None else (-1 if count is None else count)
    # -1 means the collection could not be counted at all — which happens for real: a
    # re-ingest while the API is serving resets the collection under the process, and it
    # keeps a handle that can no longer answer. Reporting ready=true alongside
    # indexed_chunks=-1 tells an orchestrator to keep sending traffic to an instance that
    # has lost its index, so a probe that cannot see its collection is not ready.
    return schemas.ReadyResponse(ready=engine is not None and n > 0, indexed_chunks=n)


@app.get("/metrics", tags=["ops"])
def metrics() -> PlainTextResponse:
    return PlainTextResponse(generate_latest(), media_type=CONTENT_TYPE_LATEST)


# --- v1 API (auth + rate limited) ---

_guarded = [Depends(require_api_key), Depends(rate_limit)]


@app.post("/v1/ask", response_model=schemas.AskResponse, dependencies=_guarded, tags=["rag"])
def ask(req: schemas.AskRequest, engine: RagEngine = Depends(get_engine)) -> schemas.AskResponse:
    top_k = req.top_k or settings.top_k

    def _grounding(result) -> schemas.GroundingReportModel | None:  # noqa: ANN001
        return (
            schemas.GroundingReportModel(**asdict(result.grounding))
            if result.grounding is not None
            else None
        )

    # Explain mode (F23): full pipeline trace, not cached (traces are for inspection).
    if req.explain:
        result, tr = engine.answer_with_trace(
            req.question, top_k, history=_to_turns(req.history), verify=req.verify
        )
        for stage, ms in result.timings_ms.items():
            ASK_LATENCY.labels(stage.replace("_ms", "")).observe(ms / 1000.0)
        return schemas.AskResponse(
            question=result.question,
            answer=result.answer,
            citations=[schemas.Citation(**c.__dict__) for c in result.citations],
            provider=engine.provider,
            timings_ms=result.timings_ms,
            trace=schemas.PipelineTraceModel(**asdict(tr)),
            grounding=_grounding(result),
        )

    cache: AnswerCache = app.state.cache
    cache_q = _cache_question(req.question, req.history)
    # A cached payload was stored without a grounding report, so serving it under
    # verify=true would silently answer "unverified" for an answer nobody verified.
    if not req.verify:
        cached = cache.get(cache_q, top_k)
        if cached is not None:
            CACHE_HITS.inc()
            return schemas.AskResponse(**cached, cached=True)

    result = engine.answer(req.question, top_k, history=_to_turns(req.history), verify=req.verify)
    for stage, ms in result.timings_ms.items():
        ASK_LATENCY.labels(stage.replace("_ms", "")).observe(ms / 1000.0)

    payload = schemas.AskResponse(
        question=result.question,
        answer=result.answer,
        citations=[schemas.Citation(**c.__dict__) for c in result.citations],
        provider=engine.provider,
        timings_ms=result.timings_ms,
        grounding=_grounding(result),
    )
    if not req.verify:
        cache.set(cache_q, top_k, payload.model_dump(exclude={"cached"}))
    return payload


@app.post("/v1/ask/stream", dependencies=_guarded, tags=["rag"])
async def ask_stream(req: schemas.AskRequest, engine: RagEngine = Depends(get_engine)):
    top_k = req.top_k or settings.top_k

    async def event_gen():
        for kind, payload in engine.stream(req.question, top_k, history=_to_turns(req.history)):
            if kind == "token":
                yield {"event": "token", "data": payload}
            else:
                cites = [schemas.Citation(**c.__dict__).model_dump() for c in payload]
                import json

                yield {"event": "citations", "data": json.dumps(cites)}
        yield {"event": "done", "data": ""}

    return EventSourceResponse(event_gen())


@app.post("/v1/ingest", response_model=schemas.IngestResponse, dependencies=_guarded, tags=["rag"])
def ingest() -> schemas.IngestResponse:
    from app.ingest import build_index

    result = build_index(settings)
    app.state.engine = build_engine()  # reload against the fresh index
    return schemas.IngestResponse(**result)


@app.get("/v1/sources", response_model=schemas.SourcesResponse, dependencies=_guarded, tags=["rag"])
def sources(engine: RagEngine = Depends(get_engine)) -> schemas.SourcesResponse:
    try:
        data = engine.vectorstore._collection.get(include=["metadatas"])  # type: ignore[attr-defined]
        counts: dict[str, int] = {}
        for md in data.get("metadatas", []) or []:
            src = (md or {}).get("source", "unknown")
            counts[src] = counts.get(src, 0) + 1
    except Exception as exc:  # noqa: BLE001
        raise HTTPException(500, f"Could not read sources: {exc}") from exc
    items = [schemas.SourceItem(source=s, chunks=c) for s, c in sorted(counts.items())]
    return schemas.SourcesResponse(sources=items, total_chunks=sum(counts.values()))


@app.post(
    "/v1/upload",
    response_model=schemas.UploadResponse,
    dependencies=_guarded,
    tags=["rag"],
)
async def upload(
    request: Request,
    filename: str = Query(..., min_length=1, description="Original file name"),
    engine: RagEngine = Depends(get_engine),
) -> schemas.UploadResponse:
    """Add one document to the live index (feature F18).

    Body is the raw file bytes (no multipart dependency); ``filename`` carries the
    name. Supported: .pdf .md .markdown .txt and images (.png/.jpg/...) via OCR (F20).
    Re-uploading the same name replaces it.
    """
    from typing import cast

    from langchain_chroma import Chroma

    from app.ingest import SUPPORTED_SUFFIXES, add_file_to_store

    safe_name = Path(filename).name  # strip any path traversal
    suffix = Path(safe_name).suffix.lower()
    if suffix not in SUPPORTED_SUFFIXES:
        raise HTTPException(415, f"Unsupported file type: {suffix or 'none'}")

    body = await request.body()
    if not body:
        raise HTTPException(400, "Empty upload")
    if len(body) > settings.max_upload_mb * 1024 * 1024:
        raise HTTPException(413, f"File exceeds {settings.max_upload_mb} MB limit")

    uploads = settings.data_dir / "uploads"
    uploads.mkdir(parents=True, exist_ok=True)
    dest = uploads / safe_name
    dest.write_bytes(body)

    try:
        # RagEngine holds the store as a VectorStore (provider seam); incremental
        # add needs Chroma's collection API, and build_engine always builds Chroma.
        added = add_file_to_store(cast(Chroma, engine.vectorstore), dest, settings)
    except ValueError as exc:
        dest.unlink(missing_ok=True)
        raise HTTPException(400, str(exc)) from exc

    # Refresh retrieval so the lexical (BM25) arm sees the new chunks (F16 + F18).
    engine.retriever = build_retriever(engine.vectorstore, settings)
    log.info("upload_indexed", filename=safe_name, chunks=added)
    return schemas.UploadResponse(
        filename=safe_name, chunks_added=added, collection=settings.active_collection_name
    )


@app.post(
    "/v1/feedback",
    response_model=schemas.FeedbackResponse,
    dependencies=_guarded,
    tags=["rag"],
)
def feedback(req: schemas.FeedbackRequest) -> schemas.FeedbackResponse:
    """Capture 👍/👎 on an answer to seed a usage-grounded eval set (feature F19)."""
    record_feedback(
        settings.feedback_path,
        question=req.question,
        answer=req.answer,
        rating=req.rating,
        comment=req.comment,
    )
    summary = feedback_summary(settings.feedback_path)
    return schemas.FeedbackResponse(ok=True, **summary)


@app.exception_handler(Exception)
async def unhandled(_, exc: Exception) -> JSONResponse:  # pragma: no cover
    log.exception("unhandled_error", error=str(exc))
    return JSONResponse(status_code=500, content={"detail": "Internal server error"})
