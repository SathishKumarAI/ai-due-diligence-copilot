# Feature Spec — F05 REST API

## Summary
Expose the RAG engine over HTTP: ask, stream, ingest, list sources, health, ready, metrics.

## Problem / why
The engine needs a stable, documented interface for the frontend and any client.

## Users & context
The Next.js UI and API clients; ops/monitoring for health + metrics.

## Behaviour (acceptance criteria)
- WHEN `POST /v1/ask {question}` THEN returns `{answer, citations[], provider, cached,
  timings_ms}` (200).
- WHEN `question` is shorter than 3 chars THEN 422 (validation).
- WHEN `POST /v1/ask/stream` THEN tokens stream via SSE, followed by a `citations` event.
- WHEN `POST /v1/ingest` THEN the index is rebuilt and the engine reloads.
- WHEN `GET /v1/sources` THEN returns each source filename and its chunk count.
- WHEN `GET /health` THEN 200 with app/version/provider (unauthenticated).
- WHEN `GET /ready` THEN reports whether the index is built.
- WHEN `GET /metrics` THEN Prometheus exposition (unauthenticated).
- WHEN the index isn't built THEN `/v1/ask` returns 503 with a clear message.

## Rules / logic
- `/v1/*` is guarded by auth (F08) + rate-limit (F08) dependencies.
- The engine is built once at startup (lifespan) and stored on `app.state`; failures
  degrade gracefully (engine = None → 503, not a crash).
- OpenAPI is auto-served at `/docs` and `/openapi.json`.

## Out of scope (for now)
- File-upload endpoint, multi-turn sessions (P2).

## Data touched
- Reads: the index. Writes: rebuilds index on `/v1/ingest`; answer cache on `/v1/ask`.

## Edge cases
- Engine unavailable · empty body · invalid `top_k` (422) · unhandled error → 500 JSON.

## Done when
- `tests/test_api.py` passes (health, ask+citations, metrics, validation, auth).
