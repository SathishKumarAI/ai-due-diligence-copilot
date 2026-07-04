# Feature Spec — F23 Pipeline trace / introspection

## Summary
Return a structured, stage-by-stage record of how an answer was produced — original vs
condensed query, tokenization, retrieved chunks with scores, the exact prompt, the answer,
and timings — so a viewer can *see how RAG works*. This is the project's differentiating,
teaching-oriented feature.

## Problem / why
RAG is a black box to most users: they see an answer and citations but not the retrieval,
ranking, or prompt behind it. Surfacing every stage builds trust for a high-stakes
investment decision and turns the app into an explainer of the pipeline itself.

## Users & context
Web-UI users via an inspector panel; programmatic callers via `explain=true` on `/v1/ask`.
The trace is produced by the engine (`app/rag.py`) and formatted by `app/trace.py`.

## Behaviour (acceptance criteria)
- WHEN `POST /v1/ask` has `explain=true` THEN the response includes a `trace`
  (`PipelineTraceModel`) alongside the normal answer + citations, and the request is
  **not cached** (traces are for live inspection).
- WHEN `explain` is false/absent THEN behaviour is identical to F03 (cached, no trace).
- WHEN history is supplied THEN the trace shows both `original_question` and
  `condensed_query`, with `condensed=true` only if they differ.
- WHEN retrieval returns nothing THEN a trace is still returned (empty `retrieved`, empty
  `user_prompt`, the guardrail answer).

## Rules / logic
- `RagEngine.answer_with_trace` mirrors `answer` but records each stage. `app/trace.py` is
  **model-free** and imports nothing from `rag.py` (engine imports trace, never the reverse) —
  no import cycle.
- Stages captured in `PipelineTrace`:
  - **Query**: `original_question` → `condensed_query` (+ `condensed` flag).
  - **Tokenization** (`TokenizationTrace`): char/word/token counts over the query using the
    lexical tokenizer `_tokenize` (regex word+number tokens) that drives the **BM25** arm,
    plus a `note` that dense embeddings use the model's subword tokenizer — labelled
    `"lexical BM25 (regex word+number tokens)"`.
  - **Retrieval** (`RetrievedChunkTrace` per chunk): rank, source, page, `extraction_method`
    (from F20), char count, best-effort `dense_score` (via `similarity_search_with_score`,
    degrading to `None` on fakes/unsupported stores), and a snippet. Also `retrieval_mode`
    (`_retrieval_mode`: hybrid if a `HybridRetriever`, else dense) and `rerank_enabled`.
  - **Prompt**: the exact `system_prompt` and `user_prompt` actually sent to the LLM, plus
    `context_char_len`.
  - **Answer + timings**: the final answer and the `timings_ms` map (condense/retrieve/generate).
- `app/main.py`'s `/v1/ask` explain branch serializes the dataclass trace with `asdict`
  into `PipelineTraceModel`; a web inspector renders the returned trace (the trace is the
  API contract the inspector consumes).

## Config / env knobs
- Per-request: `explain` (bool) on the `/v1/ask` body. No new settings; `retrieval_mode`,
  `rerank_enabled`, and `retrieve_fetch_k` are reflected in the trace.

## Out of scope (for now)
- Persisting traces / a trace history store (each is computed on demand).
- Streaming the trace (`/v1/ask/stream` returns tokens + citations only, no trace).
- Exact dense-embedding subword tokens (the tokenization view is the lexical/BM25 one).

## Data touched
- Reads: the vector store (for a best-effort dense-score probe) and in-memory pipeline
  state. Writes: none.

## Edge cases
- Fake/unsupported store with no scored search (`dense_score=None`) · empty retrieval
  (empty trace, guardrail answer) · single-turn ask (`condensed=false`, query == question) ·
  explain requests bypassing the cache entirely.

## Done when
- `explain=true` returns a populated `PipelineTraceModel` (condensed query, tokenization,
  scored chunks, exact prompt, answer, timings), explain responses are uncached, and offline
  tests cover `tokenize_trace` counts, `chunk_traces` score attachment, `dense_scores`
  degrading on a fake store, and `answer_with_trace` populating the full pipeline.
