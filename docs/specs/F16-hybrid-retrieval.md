# Feature Spec — F16 Hybrid retrieval (BM25 + dense)

## Summary
Combine lexical (BM25) and semantic (dense vector) retrieval and fuse the two
ranked lists with Reciprocal Rank Fusion (RRF), so exact figures, tickers, and
codes are recalled as well as paraphrased concepts.

## Problem / why
Dense-only retrieval misses exact-string matches (e.g. "$12.4M", "Section 4(a)",
a fund name) when the embedding blurs them. BM25 nails those but misses paraphrase.
Fusing both lifts recall on the figure/code questions investors actually ask.

## Users & context
Internal to the RAG engine on every `/v1/ask`. No API surface change beyond an
optional `retrieval_mode` already covered by config defaults.

## Behaviour (acceptance criteria)
- WHEN `retrieval_mode=hybrid` (default) THEN the engine retrieves the dense top-N
  and the BM25 top-N over the same corpus and returns the RRF-fused top-k.
- WHEN `retrieval_mode=dense` THEN behaviour is identical to F02 (dense only).
- WHEN the collection is empty THEN retrieval returns nothing (F03 guardrail).
- WHEN a query term matches a chunk lexically but not semantically THEN that chunk
  can still surface via the BM25 arm.

## Rules / logic
- BM25 is a dependency-free in-process index built from the chunk documents read
  out of the Chroma collection at engine-build time (`_collection.get`).
- Fusion: `score(d) = Σ 1/(rrf_k + rank_i(d))` across the dense and BM25 rankings;
  sort desc, take `top_k`. `rrf_k` defaults to 60 (standard).
- Each arm fetches `retrieve_fetch_k` candidates (default 20) before fusion.
- Retriever is injected into `RagEngine`; tests substitute a fake.

## Out of scope (for now)
- Cross-encoder re-ranking (F17, applied after fusion).
- Per-field / metadata-filtered retrieval.

## Data touched
- Reads: the persisted Chroma collection (vectors + documents). Writes: none.

## Edge cases
- Empty index · single-arm hit (term in only one ranking) · duplicate doc across
  arms (scores sum) · query with no lexical overlap (dense arm carries it).

## Done when
- Hybrid mode retrieves the expected source at ≥ the dense-only hit-rate on
  `eval/run_eval.py`, and unit tests cover RRF fusion + dense-only fallback.
