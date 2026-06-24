# Feature Spec — F07 Caching (answer + embedding)

## Summary
Cache embeddings (so chunks aren't re-embedded) and full answers (so identical
questions don't re-run the LLM).

## Problem / why
Embedding and generation are the slow/expensive steps. Caching cuts latency and cost,
especially for demo traffic where questions repeat.

## Users & context
Transparent to callers; toggled by `CACHE_ENABLED`.

## Behaviour (acceptance criteria)
- WHEN the same chunk is embedded again THEN it's served from the embedding cache.
- WHEN the same `(provider, question, top_k)` is asked again THEN the cached answer is
  returned with `cached: true`, without calling the LLM.
- WHEN `CACHE_ENABLED=false` THEN both caches are no-ops.
- WHEN a cached answer's TTL expires THEN it's recomputed.

## Rules / logic
- Embedding cache: `CacheBackedEmbeddings` + `LocalFileStore`, namespaced by provider+model.
- Answer cache: diskcache keyed by `sha256(provider, question.lower(), top_k)`,
  `expire=CACHE_TTL_SECONDS`. A `rag_cache_hits_total` metric increments on hit.

## Out of scope (for now)
- Cross-process/shared cache (Redis); semantic (near-duplicate) cache.

## Data touched
- Reads/Writes: `.cache/embeddings`, `.cache/answers`.

## Edge cases
- Provider change → different cache namespace/key (no stale cross-provider hits).
- Re-ingest with same question → stale answer until TTL; acceptable for this scope
  (clear `.cache/` to force-refresh).

## Done when
- Identical repeated `/v1/ask` returns `cached: true`; disabling cache returns `false`.
