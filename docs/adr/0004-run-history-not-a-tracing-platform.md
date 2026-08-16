# ADR 0004 — Run history in a JSONL file, not a tracing platform

**Status:** accepted · **Date:** 2026-08-16

## Context

ADR 0003 rejected Arize Phoenix and named Langfuse as the remaining candidate for
observability. Before evaluating Langfuse it was worth restating what was actually
missing, because "we have no observability" was not true:

- **F23** traces any single answer end to end — condensed query, tokenization, every
  retrieved chunk with its score, the exact prompt, the answer, per-stage timings.
- **F24** verifies each claim in that answer against the chunk it cites.
- **`/metrics`** exposes Prometheus counters and latency histograms.

What none of them do is **persist anything between runs**. `run_eval.py` prints a
hit-rate and the terminal scrolls. The question that could not be answered was not "what
happened in this request" — it was *"is this better or worse than last week?"*

That distinction matters, because the two problems have very different price tags.

## Decision

**Do not adopt Langfuse, or any other tracing platform. Record one JSON line per
evaluation run in `data/runs.jsonl`.**

## Why Langfuse was rejected

Its self-hosted deployment is **six services** — Postgres, ClickHouse, Redis, MinIO, a
web container and a worker — with a documented minimum of **4+ CPU cores, 16 GiB RAM and
100 GiB storage**. That is a larger installation than the RAG application it would
observe, on a project whose entire runtime is a FastAPI process and a local Chroma file.

The only lighter path is Langfuse Cloud, which needs an account and API keys. That
breaks the local-first, no-keys posture the project is built on and that `LOCAL_ONLY`
enforces in code.

Neither cost buys the missing capability. Langfuse is excellent at storing and searching
*traces*, and traces are the part already covered. Cross-run trend is a footnote of its
feature set, and it is the only part actually needed.

## What was built instead

`scripts/run_log.py` appends one line per run — timestamp, harness, git SHA, dirty flag,
the full config snapshot, and the metrics. `scripts/run_history.py` prints them with
deltas. `run_eval.py`, `run_ragas.py` and `simulate.py` all record.

Three properties were chosen deliberately:

- **Append-only.** A history that can be rewritten cannot be trusted to show a
  regression, and runs are recorded whether they passed or failed. A log that keeps only
  the good results is a marketing artifact.
- **Config travels with the metric.** `chunk_size` has already changed once in this repo
  (1000 → 400), which silently redefined every hit-rate measured before it. A number
  without its config is not comparable to the next number.
- **Git SHA *and* a dirty flag.** A metric measured on an uncommitted tree is not
  reproducible from its SHA. When git cannot be reached the flag is `null`, never
  `false`: "we could not tell" must not read as "the tree was clean".

The file is gitignored. It records what *this machine* measured, every run appends, and
committing it would conflict constantly while mixing results from different hardware and
models into one series. `docs/RUN-LOG.md` remains the curated narrative that belongs to
the repo.

## Consequences

**Gained:** cross-run trend, with zero dependencies, zero services and no keys. Verified
by running it — two evals minutes apart, hybrid then dense, produced
`faithfulness 0.600` then `0.700 (+0.100 better)` with the differing `retrieval_mode`
visible in each row.

**Given up:** trace search across many requests, a UI, multi-user history, and
per-request cost accounting. If this ever serves real traffic with real users, that
calculus changes and Langfuse should be re-examined — the decision is a judgement about
proportion at this stage, not a claim that platform tracing is worthless.

**Watch for:** `runs.jsonl` growing unbounded, and drift between what each harness
records. Both are cheap to fix and neither is a reason to add six services today.
