# Feature Spec — F04 Pluggable model providers

## Summary
Switch the LLM + embedding backend with one env var, between open-source (Ollama +
HuggingFace) and Claude (Anthropic + Voyage).

## Problem / why
The project must run free/offline by default, but also support a higher-quality paid
path — without rewrites — and stay testable offline.

## Users & context
Set by an operator via `PROVIDER`; consumed everywhere through the seam.

## Behaviour (acceptance criteria)
- WHEN `PROVIDER=ollama` THEN generation uses `llama3.1:8b` and embeddings use
  `bge-small-en-v1.5` (no API keys needed).
- WHEN `PROVIDER=claude` THEN generation uses `claude-opus-4-8` and embeddings use
  Voyage `voyage-3.5` (keys required).
- WHEN `PROVIDER` is anything else THEN `get_llm`/`get_embeddings` raise `ValueError`.
- WHEN tests run THEN they inject fakes through the same interfaces (no network).

## Rules / logic
- Only `app/providers.py` imports concrete vendor classes; everything else depends on
  LangChain `BaseChatModel` / `Embeddings` (ADR-0001).
- Vendor imports are lazy (inside the branch) so the unused provider's package isn't
  required at import time.

## Out of scope (for now)
- Additional providers (OpenAI, local vLLM) — easy to add, not needed yet.

## Data touched
- Reads: env/config. Writes: none.

## Edge cases
- Claude path with missing keys → fails at call time with a clear provider error.
- Switching provider invalidates the index (different embedding space) → re-ingest.

## Done when
- `tests/test_providers.py` passes (routing for both providers + ValueError on unknown).
