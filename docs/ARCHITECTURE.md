---
title: Architecture
description: System shape, data flow, and the decisions behind them. Tier: Core.
sidebar_position: 3
---

# Architecture

> One RAG engine behind a FastAPI service and a Next.js UI. The whole design hangs
> on one seam: **everything depends on LangChain interfaces, never a vendor class.**

## Context / Why

We need answers a user can *trust* over private documents: grounded in real
passages, traceable to a source, and runnable with no paid API keys. That drives
three choices — local Chroma, a provider seam, and citations from retrieval
metadata (not the model's imagination).

## Overview

```
                      ┌────────────────────────┐
  data/ (pdf/md/txt) ─►  ingest.py             │  load → split → embed → Chroma
                      └────────────────────────┘
                                  │ persisted vectors (chroma_db/)
                                  ▼
  question ─► RagEngine.answer():  retrieve top-k ─► prompt+context ─► LLM
                                  │                                     │
                                  └──► citations from chunk metadata ◄──┘
                                  ▼
                        FastAPI /v1/ask  ◄── Next.js web/ (Ask + What's New)
```

## Components

| Module | Responsibility |
|--------|----------------|
| `app/config.py` | All settings (pydantic-settings); the `PROVIDER` switch |
| `app/providers.py` | **The seam.** `get_llm` / `get_embeddings` per provider |
| `app/ingest.py` | Load → chunk → embed → persist (idempotent rebuild) |
| `app/rag.py` | `RagEngine`: retrieve → prompt → LLM → answer + citations + timings |
| `app/cache.py` | Embedding cache + answer cache (diskcache) |
| `app/security.py` | API-key auth + token-bucket rate limiting |
| `app/observability.py` | JSON logging, request IDs, Prometheus metrics |
| `app/main.py` | FastAPI wiring, `/v1` routes, streaming, ops endpoints |
| `web/` | Next.js UI for non-technical users |

## Data flow (a request)

1. `POST /v1/ask` → auth + rate-limit dependencies.
2. Answer cache checked (key = provider + question + top_k).
3. `RagEngine.answer`: `similarity_search(k)` → numbered context → `llm.invoke`.
4. Citations parsed from `[n]` markers in the answer, mapped to retrieved chunks'
   metadata (source, page, snippet).
5. Result cached; metrics + structured log emitted with a request id.

## Key decisions (see `adr/`)

- **Provider abstraction** ([ADR-0001](adr/0001-provider-abstraction.md)) — enables
  the free/paid switch *and* offline tests.
- **Citations from retrieval metadata** ([ADR-0002](adr/0002-citations-from-retrieval-metadata.md))
  — a citation always traces to a real chunk, never a hallucinated reference.

## Gotchas

- First `ingest` with the Ollama provider downloads the HF embedding model.
- Chroma is local/single-node; not built for horizontal scale (fine for this scope).
- Switching `PROVIDER` changes the embedding space → **re-ingest** before querying.
