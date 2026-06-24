# Feature Spec — F02 Retrieval + vector store

## Summary
Given a question, return the `top_k` most relevant chunks from the Chroma collection.

## Problem / why
The LLM can only ground its answer in text it's given. Retrieval selects that text.

## Users & context
Called internally by the RAG engine on every `/v1/ask`.

## Behaviour (acceptance criteria)
- WHEN a question is asked THEN the engine returns the `top_k` chunks most similar to it.
- WHEN `top_k` is provided on the request THEN it overrides the default (bounded 1–20).
- WHEN the collection is empty THEN retrieval returns nothing and the engine returns
  the no-data guardrail (see F03).

## Rules / logic
- `Chroma.similarity_search(question, k)`; `k = request.top_k or settings.top_k`.
- Retrieved `Document`s retain `source`/`page` metadata for citations (F03).

## Out of scope (for now)
- Hybrid (BM25 + dense) retrieval and cross-encoder re-ranking (P2).

## Data touched
- Reads: the persisted Chroma collection. Writes: none.

## Edge cases
- Empty index · `top_k` larger than collection size (returns whatever exists) ·
  provider mismatch with index (different embedding space → re-ingest, see RUNBOOK).

## Done when
- The engine retrieves the expected source for eval questions at ≥ 70% hit-rate
  (`eval/run_eval.py`).
