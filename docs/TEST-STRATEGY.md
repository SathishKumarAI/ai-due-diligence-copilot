---
title: Test strategy
description: What we test, at what level, and the offline-first rule. Tier: Growing.
sidebar_position: 6
---

# Test strategy

> The non-negotiable rule: **tests run offline.** No network, no model download, no
> API keys. The provider seam (`app/providers.py`) is what makes that possible —
> tests inject a deterministic fake embedder and a fake chat model.

## Levels

| Level | What | Where |
|-------|------|-------|
| Unit | chunking, citation mapping, provider routing | `tests/test_chunking.py`, `test_citations.py`, `test_providers.py` |
| Integration | the HTTP surface end-to-end with a fake engine | `tests/test_api.py` (FastAPI `TestClient`) |
| Eval (quality) | retrieval hit-rate + answer faithfulness | `eval/run_eval.py` (needs a real provider; CI gate) |

## The fakes

- `DeterministicFakeEmbeddings` — hashing bag-of-words → stable vectors; shared words
  rank higher, enough for a real `similarity_search` over an in-memory Chroma.
- `FakeChat` — returns a fixed grounded answer citing `[1]`; supports `.stream()`.

See `tests/conftest.py`.

## What each layer proves

- Unit: the *logic* is correct regardless of model — citation markers map to the
  right chunk, the no-data guardrail fires, the provider factory routes correctly.
- Integration: auth, validation, metrics, and the response shape are correct.
- Eval: the *retrieval + prompt* actually produce grounded, on-target answers — run
  against Ollama or Claude, gated in CI at hit-rate ≥ 70% / faithfulness ≥ 70%.

## Running

```bash
make test       # unit + integration (offline)
make lint       # ruff
make typecheck  # mypy
make eval       # quality gate (requires a provider + a built index)
```

## Gotcha

The eval suite is the only test layer that needs a live model; keep it out of the
fast `make test` loop. CI runs `make test` on every push and `eval` where a provider
is available.
