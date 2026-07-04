# Feature Spec — F17 Re-ranker (cross-encoder)

## Summary
After retrieval, re-score the candidate chunks with a cross-encoder that reads the
(question, chunk) pair jointly, then keep the sharpest `top_k` for generation.

## Problem / why
Bi-encoder retrieval (dense or hybrid) ranks chunks by an approximate similarity.
A cross-encoder reads the question and chunk together and is far more precise about
relevance — moving the genuinely-answering passage into the top few the LLM sees.

## Users & context
Internal to the RAG engine, between retrieval (F02/F16) and prompt assembly (F03).

## Behaviour (acceptance criteria)
- WHEN `rerank_enabled=true` THEN the engine fetches `retrieve_fetch_k` candidates,
  re-scores them with the cross-encoder, and passes the re-ranked `top_k` to the LLM.
- WHEN `rerank_enabled=false` (default) THEN candidates pass through unchanged.
- WHEN fewer candidates than `top_k` exist THEN all are returned, re-ordered.
- WHEN the corpus is empty THEN no rerank runs (F03 guardrail).

## Rules / logic
- `Reranker` protocol: `rerank(query, docs, top_n) -> list[Document]`.
- `CrossEncoderReranker` uses `sentence-transformers` `CrossEncoder` (already a
  dependency); default model `cross-encoder/ms-marco-MiniLM-L-6-v2`, loaded lazily
  and cached. `NoOpReranker` for the disabled path and for offline tests.
- The reranker is injected into `RagEngine`; tests substitute a fake that sorts by a
  deterministic rule, so CI never downloads a model.

## Out of scope (for now)
- Provider-hosted rerankers (e.g. Voyage rerank) — the seam allows adding one later.

## Data touched
- Reads: retrieved chunks in memory. Writes: none. (Model weights cached on disk
  by sentence-transformers on first use.)

## Edge cases
- Empty candidate list · ties (stable order) · `top_n` larger than candidates.

## Done when
- With rerank enabled, the answering passage lands in the top-`top_k` at ≥ the
  no-rerank hit-rate on `eval/run_eval.py`; unit tests cover ordering + disabled path.
