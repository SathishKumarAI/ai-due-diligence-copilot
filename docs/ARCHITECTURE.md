---
title: Architecture
description: System architecture and ML view — components, request lifecycle, the provider seam, and the model layer.
sidebar_position: 3
---

# Architecture

> One RAG engine behind a FastAPI service and a Next.js UI. The whole design hangs on one
> seam: **everything depends on LangChain interfaces, never a vendor class.** That seam is
> what makes the free↔paid provider switch *and* fully offline tests possible.
>
> For the stage-by-stage RAG walkthrough see [`HOW-RAG-WORKS.md`](HOW-RAG-WORKS.md); for
> the offline ingest half see [`INGESTION.md`](INGESTION.md). This doc is the system +
> ML-pipeline view.

## Context / why these choices

We need answers a user can *trust* over private deal documents: grounded in real
passages, traceable to a source, and runnable with no paid API keys. Three consequences:

1. **Local Chroma** — a persistent vector DB that needs no server.
2. **A provider seam** (`app/providers.py`) — depend on interfaces, so the model backend
   is a single env var and tests inject fakes.
3. **Citations from retrieval metadata** — a `[n]` marker always maps to a real chunk,
   never a hallucinated reference.

---

## Components

| Module | Responsibility |
|---|---|
| `app/config.py` | All settings via pydantic-settings; the `PROVIDER` / `LLM_PROVIDER` / `EMBED_PROVIDER` switches, the model-keyed collection name, and every tunable |
| `app/providers.py` | **The seam.** `get_llm` / `get_embeddings` return LangChain interfaces per provider |
| `app/ingest.py` | Load → clean → split → dedupe → embed → persist (idempotent rebuild) |
| `app/ocr.py` | OCR for images + scanned PDFs (Tesseract, F20) |
| `app/cleaning.py` | Deterministic text normalization + near-dup chunk removal (F21) |
| `app/retrieval.py` | `DenseRetriever`, `BM25Index`, `HybridRetriever`, RRF fusion (F16) |
| `app/rerank.py` | Cross-encoder reranker + no-op fallback (F17) |
| `app/rag.py` | `RagEngine`: condense → retrieve → rerank → prompt → LLM → answer + citations + trace |
| `app/trace.py` | Pipeline introspection trace (F23) |
| `app/prompts.py` | Domain system prompt + follow-up condense prompt |
| `app/cache.py` | Embedding cache + answer cache (diskcache) |
| `app/security.py` | API-key auth + token-bucket rate limiting |
| `app/observability.py` | JSON logging, request IDs, Prometheus metrics |
| `app/feedback.py` | 👍/👎 capture to seed an eval set (F19) |
| `app/main.py` | FastAPI wiring, `/v1` routes, streaming, ops endpoints |
| `web/` | Next.js UI (Ask page + "What's New") |

### System diagram

```mermaid
flowchart TB
    subgraph client["Clients"]
        UI["Next.js web/ (Ask + What's New)"]
        CURL["curl / API consumers"]
    end

    subgraph api["FastAPI app (app/main.py)"]
        MW["middleware: request-id, logging, metrics, CORS"]
        AUTH["security.py: API-key + rate-limit"]
        ROUTES["/v1/ask, /v1/ask/stream, /v1/ingest, /v1/upload, /v1/sources, /v1/feedback"]
        OPS["/health, /ready, /metrics"]
    end

    subgraph engine["RagEngine (app/rag.py)"]
        RETR["Retriever (dense | hybrid)"]
        RERANK["Reranker (cross-encoder | no-op)"]
        LLM["chat model (invoke / stream)"]
        TRACE["trace.py (F23)"]
    end

    subgraph infra["State + models"]
        CHROMA[("Chroma vector DB (chroma_db/)")]
        CACHE[("diskcache: embeddings + answers (.cache/)")]
        PROV["providers.py — the seam"]
        OLL["Ollama: llama3.1 + bge-small (local GPU)"]
        CLOUD["Claude + Voyage (cloud, optional)"]
    end

    UI --> MW
    CURL --> MW
    MW --> AUTH --> ROUTES
    MW --> OPS
    ROUTES --> engine
    RETR --> CHROMA
    RETR --> RERANK --> LLM
    LLM --> TRACE
    ROUTES --> CACHE
    engine --> PROV
    PROV --> OLL
    PROV --> CLOUD
    OPS --> CHROMA
```

---

## Request lifecycle

The engine is built **once at startup** (`build_engine` in `lifespan`) and stored on
`app.state`, so requests are cheap and tests can swap in a fake engine. If the index
isn't built yet, startup degrades gracefully (`engine = None`) and `/v1/*` returns `503`
until you ingest.

A non-streaming `POST /v1/ask` (single turn, cache miss):

```mermaid
sequenceDiagram
    autonumber
    participant C as Client
    participant MW as Middleware
    participant Sec as security.py
    participant API as /v1/ask (main.py)
    participant Cache as AnswerCache
    participant Eng as RagEngine
    participant R as Retriever (hybrid)
    participant Ch as Chroma
    participant RR as Reranker
    participant M as chat model

    C->>MW: POST /v1/ask {question}
    MW->>MW: bind request-id, start timer
    MW->>Sec: require_api_key + rate_limit
    Sec-->>API: authorized
    alt explain=true (F23)
        API->>Eng: answer_with_trace(question)
        Note over Eng: not cached — traces are for inspection
    else normal
        API->>Cache: get(provider+question+top_k)
        Cache-->>API: miss
        API->>Eng: answer(question)
    end
    Eng->>Eng: _condense (only if history)
    Eng->>R: retrieve(query, fetch_k)
    R->>Ch: dense similarity_search
    R->>R: BM25 lexical search + RRF fuse
    R-->>Eng: candidate chunks
    Eng->>RR: rerank(query, candidates, top_k)
    RR-->>Eng: top_k chunks
    Eng->>Eng: _format_context ([1]..[n]) + _build_messages
    Eng->>M: invoke(system + context + question)
    M-->>Eng: answer text with [n] markers
    Eng->>Eng: _citations: map [n] -> chunk metadata
    Eng-->>API: Answer + citations + timings
    API->>Cache: set(...) (skipped for explain mode)
    API->>MW: response
    MW->>MW: record metrics + JSON log, add x-request-id
    MW-->>C: 200 {answer, citations, provider, timings, trace?}
```

Notes worth internalizing:

- **Auth/limit are dependencies** on the `/v1/*` routes (`_guarded`). If `API_KEY` is
  empty (local default), auth is a no-op; rate limiting is per key (or client IP).
- **Answer cache** keys on `sha256(provider, question, top_k)`; follow-ups fold history
  into the key so they don't collide with the same words asked cold. **Explain mode
  bypasses the cache** entirely.
- **Streaming** (`/v1/ask/stream`) uses SSE: `engine.stream` yields `token` events then a
  final `citations` event and `done` — same retrieval, incremental generation.
- Middleware emits a Prometheus counter/histogram and a structured JSON log per request,
  and per-stage `ASK_LATENCY` (`condense` / `retrieve` / `generate`).

---

## The provider seam

Everything upstream of `providers.py` depends on **LangChain abstractions**
(`BaseChatModel`, `Embeddings`) — never `ChatOllama`, `ChatAnthropic`, etc. directly. One
factory decides the concrete class per provider, and imports are lazy so an unused
backend's package need not be installed (or reachable) to run or test.

**The seam has two halves.** `get_llm` follows `LLM_PROVIDER` and `get_embeddings`
follows `EMBED_PROVIDER`, each falling back to `PROVIDER` when unset. Mixing is the
point: the generator and the embedder answer to different constraints — one is a quality
and cost decision made per question, the other is a decision baked into every vector in
the store — and welding them to one switch forced a re-embed of the whole corpus just to
try a different model.

```mermaid
flowchart LR
    CFG["config.py: PROVIDER<br/>LLM_PROVIDER / EMBED_PROVIDER"] --> PF["providers.get_llm / get_embeddings"]
    PF -->|ollama| O["ChatOllama (llama3.1:8b)<br/>HuggingFaceEmbeddings (bge-small)"]
    PF -->|claude| A["ChatAnthropic (claude-opus-4-8)<br/>VoyageAIEmbeddings (voyage-3.5)"]
    PF -->|openai| X["ChatOpenAI + OpenAIEmbeddings<br/>against OPENAI_BASE_URL"]
    X -.-> V["OpenAI · Groq · Together · DeepSeek<br/>vLLM · TGI · LM Studio"]
    O -.returns.-> IFACE["BaseChatModel / Embeddings interfaces"]
    A -.returns.-> IFACE
    X -.returns.-> IFACE
    IFACE --> ENG["RagEngine + ingest depend ONLY on these interfaces"]
    FAKE["tests inject fakes implementing the same interfaces"] --> ENG
```

Why it matters:

| Benefit | How the seam delivers it |
|---|---|
| Free↔paid switch | one env var `PROVIDER=ollama\|claude\|openai`; no code change |
| Mix the halves | `LLM_PROVIDER=claude` with `EMBED_PROVIDER=ollama` — a strong generator over an index you already built |
| One adapter, many vendors | everything that speaks the OpenAI wire format is reached by changing `OPENAI_BASE_URL`, not by adding code |
| Offline CI | tests inject fake `BaseChatModel` / `Embeddings` / `Retriever` / `Reranker` — no network, no model download |
| Swap retrieval / rerank | `RagEngine` takes a `Retriever` and `Reranker` **protocol**; `build_retriever` / `build_reranker` pick the impl by config |
| Trustworthy citations | `RagEngine` never sees a vendor response shape — it works off `Document` metadata |

**`LOCAL_ONLY` is judged by endpoint, not by name.** `claude` is always cloud and
`ollama` never is, but `openai` is either, depending on where it points — vLLM, TGI, LM
Studio and Ollama all serve the same wire format on localhost. The guard resolves the
host in `OPENAI_BASE_URL` against `config.LOCAL_HOSTS`, and refuses only the half that
selected a cloud endpoint, so a local generator with cloud embeddings fails on the
embeddings alone rather than taking down the app.

> **Consequence:** each embedding model has its **own vector space**, so each gets its own
> Chroma collection, named `{COLLECTION_NAME}_{hash(embed_provider:embed_model)}`.
> Changing the embedding model selects an empty collection and `/health` reports the
> corpus as unindexed — **re-ingest**. Before this was enforced the index was silently
> reused across models, which raises on a dimension change and, at matching dimensions,
> does not raise at all. Changing the *LLM* half leaves the index alone.

---

## The ML pipeline view

RAG here is really **four models/algorithms** stacked, each doing one job. Three are
swappable behind interfaces; one (BM25) is a dependency-free algorithm baked in.

```mermaid
flowchart TD
    subgraph ingest["Ingest-time model"]
        E["Embedding model — bge-small-en-v1.5 (local) OR voyage-3.5 (cloud)<br/>chunk text -> dense vector; subword tokenizer inside"]
    end
    E --> V[("Chroma: vectors + metadata")]

    subgraph query["Query-time stack"]
        direction TB
        BM["BM25Index (Okapi BM25, k1=1.5 b=0.75)<br/>lexical tokens; exact terms, tickers, 40% figures<br/>NO model — pure algorithm, in-process"]
        DR["DenseRetriever<br/>same embedding model, semantic match via Chroma"]
        RRF["Reciprocal Rank Fusion (rrf_k=60)<br/>fuse ranks, not scores"]
        CE["CrossEncoderReranker (optional)<br/>ms-marco-MiniLM-L-6-v2<br/>reads (question, chunk) jointly, re-scores"]
        GEN["Generator LLM<br/>llama3.1:8b (temp 0) OR claude-opus-4-8<br/>writes grounded answer + [n] markers"]
    end

    V --> DR
    BM --> RRF
    DR --> RRF
    RRF --> CE
    CE --> GEN
```

| Layer | Model / algorithm | Role | Trainable objective it exploits | Config |
|---|---|---|---|---|
| Embedding | `bge-small-en-v1.5` / `voyage-3.5` | text → vector (semantic) | contrastive sentence similarity | `HF_EMBED_MODEL` / `VOYAGE_MODEL` |
| Lexical | Okapi BM25 (`BM25Index`) | exact-term ranking | TF·IDF with length normalization | `k1=1.5, b=0.75` (in code) |
| Fusion | Reciprocal Rank Fusion | merge dense + lexical rankings | rank-only, scale-free | `RRF_K`, `RETRIEVE_FETCH_K` |
| Rerank | cross-encoder MiniLM | precise (q, chunk) relevance | pairwise relevance (MS MARCO) | `RERANK_ENABLED`, `RERANK_MODEL` |
| Generation | `llama3.1:8b` / `claude-opus-4-8` | grounded answer + citations | instruction-following chat | `OLLAMA_LLM_MODEL` / `ANTHROPIC_MODEL`, `MAX_TOKENS` |

**Why this specific stack?** Dense retrieval catches *meaning* but blurs exact
figures/names; BM25 catches *exact terms* but misses paraphrase — hybrid + RRF gets both.
The cross-encoder is the precision layer (expensive, so opt-in) that promotes the truly
answering passage. The generator is deliberately constrained by the system prompt to
*only* summarize the retrieved passages and cite them — its temperature is `0` on the
local path for determinism.

---

## Local-first by default, cloud optional

| | Default (local-first) | Optional (cloud) |
|---|---|---|
| `PROVIDER` | `ollama` | `claude` |
| LLM | `llama3.1:8b` on **Ollama** (RTX GPU on the run host) | `claude-opus-4-8` |
| Embeddings | `bge-small-en-v1.5` (HuggingFace, local) | Voyage `voyage-3.5` |
| Keys needed | none | `ANTHROPIC_API_KEY`, `VOYAGE_API_KEY` |
| Runs offline | yes (after first model download) | no |

Keys live **only in a gitignored local `.env`** (`config.py` loads via pydantic-settings;
`api_key`, `anthropic_api_key`, `voyage_api_key` default to empty). The whole app is built
to run free and offline first; the cloud path is a one-env-var upgrade, not a rewrite.

---

## Key decisions (see `adr/`)

- **Provider abstraction** ([ADR-0001](adr/0001-provider-abstraction.md)) — the seam
  above; enables the free/paid switch *and* offline tests.
- **Citations from retrieval metadata** ([ADR-0002](adr/0002-citations-from-retrieval-metadata.md))
  — a citation always traces to a real chunk, never a hallucinated reference.

## Gotchas

- First ingest with the Ollama provider **downloads the HF embedding model** (once).
- Chroma is local/single-node — not built for horizontal scale (fine for this scope).
- Switching `PROVIDER` changes the embedding space → **re-ingest** before querying.
- BM25 is built from a **snapshot** of the collection; `/v1/upload` rebuilds the retriever
  so the lexical arm sees new chunks (the dense arm reads Chroma live).
- The `dense_score` in an F23 trace is Chroma's **distance** (lower = closer), not a 0–1
  similarity, and reflects only the dense arm — not the RRF order that actually ranked the
  chunks.
