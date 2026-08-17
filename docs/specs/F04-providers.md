# Feature Spec — F04 Pluggable model providers

## Summary
Switch the LLM and embedding backends with env vars, across open-source (Ollama +
HuggingFace), Claude (Anthropic + Voyage), and any OpenAI-compatible endpoint. The two
halves are chosen independently, so a local generator can run against cloud embeddings
or the reverse.

## Problem / why
The project must run free/offline by default, but also support higher-quality paid
paths — without rewrites — and stay testable offline.

A single switch could not express the combinations that matter. `PROVIDER=claude` forced
Voyage embeddings even when the local `bge-small` index was the one already built, and
there was no way to try a stronger generator against an existing vector store without
re-embedding the whole corpus. The seam was in the right place; it was just too coarse.

## Users & context
Set by an operator via `PROVIDER`, optionally refined by `LLM_PROVIDER` and
`EMBED_PROVIDER`; consumed everywhere through the seam.

## Behaviour (acceptance criteria)
- WHEN `PROVIDER=ollama` THEN generation uses `llama3.1:8b` and embeddings use
  `bge-small-en-v1.5` (no API keys needed).
- WHEN `PROVIDER=claude` THEN generation uses `claude-opus-4-8` and embeddings use
  Voyage `voyage-3.5` (keys required).
- WHEN `PROVIDER=openai` THEN both halves use the OpenAI client, against
  `OPENAI_BASE_URL` if set and `api.openai.com` otherwise.
- WHEN `LLM_PROVIDER` or `EMBED_PROVIDER` is set THEN that half uses it and the other
  half still follows `PROVIDER`.
- WHEN neither is set THEN both follow `PROVIDER` — the original single-switch behaviour
  is unchanged, and every existing `.env` keeps working.
- WHEN a provider name is unrecognised THEN `get_llm`/`get_embeddings` raise `ValueError`
  — not a `LOCAL_ONLY` refusal, which would misreport an unknown name as a policy block.
- WHEN `LOCAL_ONLY=true` (the default) AND a half selects a cloud provider THEN that half
  raises `RuntimeError`, naming the half and the endpoint. The other half is unaffected.
- WHEN `LOCAL_ONLY=true` AND `PROVIDER=openai` points at a local host THEN it is allowed:
  vLLM, TGI, LM Studio and Ollama all serve the OpenAI wire format on localhost, and
  refusing them would refuse a fully-local setup.
- WHEN the embedding provider or model changes THEN a different Chroma collection is
  selected, so `/health` reports an unindexed corpus rather than answering from vectors
  a different model produced.
- WHEN tests run THEN they inject fakes through the same interfaces (no network).

## Rules / logic
- Only `app/providers.py` imports concrete vendor classes; everything else depends on
  LangChain `BaseChatModel` / `Embeddings` (ADR-0001).
- Vendor imports are lazy (inside the branch) so the unused provider's package isn't
  required at import time.
- "Cloud" is a property of the endpoint, not the provider name. `claude` is always cloud,
  `ollama` never is, and `openai` is decided by the host in `OPENAI_BASE_URL` against
  `config.LOCAL_HOSTS`.
- The embedding half owns the vector store identity and the embedding cache namespace;
  the LLM half owns the answer cache identity. Neither reads the other's model name.

## Out of scope (for now)
- Google Gemini — the one major vendor that does not speak the OpenAI wire format, so it
  needs its own adapter and `langchain-google-genai`. Separate change.
- A model-comparison harness that sweeps combinations through `make eval`. `make eval`
  with a different `.env` already does one run; a sweep over four synthetic documents
  would be measuring noise. Add it when the corpus is real.
- Per-request provider selection. Provider is process-level configuration.

## Data touched
- Reads: env/config. Writes: none directly — but the embedding half determines which
  Chroma collection `app/ingest.py` creates and `app/main.py` reads.

## Edge cases
- Cloud path with missing keys → fails at call time with a clear provider error.
- OpenAI-compatible local servers usually want no key; a placeholder is sent because the
  client requires the field, and a local backend ignores it.
- Changing the embedding model no longer silently reuses the old index. It selects a new
  collection, which starts empty and needs an ingest. **The previous collection is left
  on disk**, not deleted — it is the only copy of that model's vectors. Remove it by hand
  if the disk matters.
- A `COLLECTION_NAME` long enough to overflow Chroma's 63-character ceiling is truncated
  before the model fingerprint is appended.

## Done when
- `tests/test_providers.py` passes: routing for all three providers, the split defaulting
  to `PROVIDER`, per-half `LOCAL_ONLY` gating, localhost-vs-vendor classification for the
  OpenAI adapter, `ValueError` on an unknown name, and collection-name derivation.
