# ADR-0001: Abstract the model provider behind a seam

- **Status:** Accepted
- **Date:** 2026-06-23

## Context

We want the project to run **free and offline** by default (open-source models) but
also support Claude for quality. We also need tests that run in CI without network
access or model downloads.

## Decision

Introduce a single seam, `app/providers.py`, exposing `get_llm(settings)` and
`get_embeddings(settings)` that return LangChain `BaseChatModel` / `Embeddings`
implementations chosen by a `PROVIDER` env var. **No other module imports a concrete
vendor class.** The `RagEngine` is constructed with these interfaces (dependency
injection), so tests can pass fakes.

## Consequences

- ✅ One env var switches `ollama` ↔ `claude`; no code change.
- ✅ Offline tests inject `DeterministicFakeEmbeddings` + `FakeChat` — the whole RAG
  path runs in CI with no network.
- ✅ Adding a provider = one branch in two functions.
- ⚠️ Switching providers changes the embedding space → the index must be rebuilt.
- ⚠️ The lowest common denominator of the LangChain interfaces is what we can use;
  provider-specific features (e.g. Claude native citations) are intentionally avoided
  to keep the seam clean (see ADR-0002).
