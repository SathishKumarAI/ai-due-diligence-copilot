"""FastAPI application (feature F05): /v1 routes, auth, metrics, streaming.

The RAG engine is built once at startup and stored on app.state, so requests are
cheap and tests can override the dependency with a fake engine.
"""
from __future__ import annotations

from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from fastapi import Depends, FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse, PlainTextResponse
from prometheus_client import CONTENT_TYPE_LATEST, generate_latest
from sse_starlette.sse import EventSourceResponse

from app import schemas
from app.cache import AnswerCache, wrap_embeddings
from app.config import settings
from app.observability import (
    ASK_LATENCY,
    CACHE_HITS,
    RequestContextMiddleware,
    configure_logging,
    log,
)
from app.providers import get_embeddings, get_llm
from app.rag import RagEngine
from app.security import rate_limit, require_api_key


def build_engine() -> RagEngine:
    """Construct the production engine from the configured provider + index."""
    from app.ingest import load_index

    embeddings = wrap_embeddings(get_embeddings(settings), settings)
    store = load_index(settings, embeddings)
    llm = get_llm(settings)
    return RagEngine(store, llm, top_k=settings.top_k, provider=settings.provider)


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    configure_logging()
    app.state.cache = AnswerCache(settings)
    try:
        app.state.engine = build_engine()
        log.info("engine_ready", provider=settings.provider)
    except Exception as exc:  # noqa: BLE001 - degrade gracefully if not yet ingested
        app.state.engine = None
        log.warning("engine_unavailable", error=str(exc))
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
    engine = getattr(app.state, "engine", None)
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
        provider=settings.provider,
    )


@app.get("/ready", response_model=schemas.ReadyResponse, tags=["ops"])
def ready() -> schemas.ReadyResponse:
    engine = getattr(app.state, "engine", None)
    n = 0
    if engine is not None:
        try:
            n = engine.vectorstore._collection.count()  # type: ignore[attr-defined]
        except Exception:  # noqa: BLE001
            n = -1
    return schemas.ReadyResponse(ready=engine is not None and n != 0, indexed_chunks=n)


@app.get("/metrics", tags=["ops"])
def metrics() -> PlainTextResponse:
    return PlainTextResponse(generate_latest(), media_type=CONTENT_TYPE_LATEST)


# --- v1 API (auth + rate limited) ---

_guarded = [Depends(require_api_key), Depends(rate_limit)]


@app.post("/v1/ask", response_model=schemas.AskResponse, dependencies=_guarded, tags=["rag"])
def ask(req: schemas.AskRequest, engine: RagEngine = Depends(get_engine)) -> schemas.AskResponse:
    top_k = req.top_k or settings.top_k
    cache: AnswerCache = app.state.cache
    cached = cache.get(req.question, top_k)
    if cached is not None:
        CACHE_HITS.inc()
        return schemas.AskResponse(**cached, cached=True)

    result = engine.answer(req.question, top_k)
    for stage, ms in result.timings_ms.items():
        ASK_LATENCY.labels(stage.replace("_ms", "")).observe(ms / 1000.0)

    payload = schemas.AskResponse(
        question=result.question,
        answer=result.answer,
        citations=[schemas.Citation(**c.__dict__) for c in result.citations],
        provider=engine.provider,
        timings_ms=result.timings_ms,
    )
    cache.set(req.question, top_k, payload.model_dump(exclude={"cached"}))
    return payload


@app.post("/v1/ask/stream", dependencies=_guarded, tags=["rag"])
async def ask_stream(req: schemas.AskRequest, engine: RagEngine = Depends(get_engine)):
    top_k = req.top_k or settings.top_k

    async def event_gen():
        for kind, payload in engine.stream(req.question, top_k):
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


@app.exception_handler(Exception)
async def unhandled(_, exc: Exception) -> JSONResponse:  # pragma: no cover
    log.exception("unhandled_error", error=str(exc))
    return JSONResponse(status_code=500, content={"detail": "Internal server error"})
