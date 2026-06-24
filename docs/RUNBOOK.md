---
title: Runbook
description: Operate, deploy, and troubleshoot the service. Tier: Growing.
sidebar_position: 8
---

# Runbook

> How to run, deploy, and fix the service. Environments + the common failure modes.

## Environments / config

| Variable | Default | Purpose |
|----------|---------|---------|
| `PROVIDER` | `ollama` | `ollama` (free/local) or `claude` |
| `OLLAMA_BASE_URL` | `http://localhost:11434` | Ollama daemon |
| `OLLAMA_LLM_MODEL` | `llama3.1:8b` | generation model |
| `HF_EMBED_MODEL` | `BAAI/bge-small-en-v1.5` | embeddings |
| `ANTHROPIC_API_KEY` / `VOYAGE_API_KEY` | — | required only for `claude` |
| `API_KEY` | empty (open) | gates `/v1/*` when set |
| `RATE_LIMIT_PER_MIN` | `60` | per key/IP |
| `CACHE_ENABLED` / `CACHE_TTL_SECONDS` | `true` / `3600` | answer + embedding cache |

## Deploy

### Docker compose (backend + Ollama)
```bash
docker compose up --build
docker compose exec ollama ollama pull llama3.1:8b   # one-time
docker compose exec api python -m app.ingest          # build the index
```

### Frontend (Vercel)
Deploy `web/` to Vercel; set `NEXT_PUBLIC_API_BASE_URL` to the backend URL and
`NEXT_PUBLIC_GITHUB_REPO`. Backend can run on any container host.

## Operate

- Health: `GET /health` (liveness), `GET /ready` (index built?).
- Metrics: `GET /metrics` (Prometheus) — `rag_requests_total`,
  `rag_request_latency_seconds`, `rag_ask_stage_seconds`, `rag_cache_hits_total`.
- Logs: structured JSON with a `request_id` per request.

## Troubleshooting

| Symptom | Cause | Fix |
|---------|-------|-----|
| `503 Index not built` | no `chroma_db/` | run `python -m app.ingest` |
| `/ready` shows 0 chunks | empty/!ingested corpus | add docs to `data/`, re-ingest |
| Answers ignore a new doc | switched `PROVIDER` (different embed space) | re-ingest |
| Connection refused (ollama) | daemon down / wrong URL | start Ollama; check `OLLAMA_BASE_URL` |
| `401` from `/v1/*` | `API_KEY` set, header missing | send `X-API-Key` |
| `429` | rate limit hit | back off or raise `RATE_LIMIT_PER_MIN` |
| Slow first ingest | HF model download | one-time; subsequent runs are cached |
