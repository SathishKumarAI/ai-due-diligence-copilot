# ADR 0003 — Ragas yes, Arize Phoenix no

**Status:** accepted · **Date:** 2026-08-16

## Context

We wanted two things from the open-source LLM tooling ecosystem: multi-dimensional RAG
evaluation, and tracing that shows what the model actually received. The agreed
constraint was that both stay **dev-only** — in `requirements-dev.txt`, never imported by
`app/`, never in the shipped image — so the product keeps its local-first, no-keys,
dependency-light character.

Ragas and Arize Phoenix were the two candidates the research pointed at. Ragas is the
most widely adopted RAG evaluation framework; Phoenix is the strongest open-source
option for local RAG tracing and runs in-process without extra infrastructure.

## Decision

**Adopt Ragas. Do not adopt Arize Phoenix.**

## Why Phoenix was rejected

Both problems were found by installing it and running the suite, not by reading docs.

**1. It hooks pytest for every run.** `arize-phoenix-client` registers a `pytest11`
entry point:

```
arize-phoenix-client: phoenix = phoenix.client.pytest.plugin
```

pytest auto-loads plugins from that group, so merely having Phoenix installed makes
every `pytest` invocation import Phoenix — including the offline unit suite that
deliberately touches no model, no network and no observability stack. A dev-only
observability tool that inserts itself into the core test path is not dev-only. That
alone breaks the boundary this ADR exists to protect.

**2. The locked version is broken as published.** `arize-phoenix==11.38.0` imports
`pytz` at module scope but does not declare it as a dependency:

```
arize-phoenix:        declares pytz -> NO
arize-phoenix-client: declares pytz -> NO
pytz in requirements-dev.lock: absent
```

Combined with (1), installing Phoenix took the whole suite from 85 passing to a
collection-time `ModuleNotFoundError: No module named 'pytz'`. The lockfile is not at
fault — uv locked exactly what the package declared. Working around it would mean
pinning an undeclared transitive dependency by hand and carrying that indefinitely.

Note the version: `pip install arize-phoenix` takes 20.2.1, but the resolver caps it at
11.38.0 against our stack. So the version that actually resolves here is the broken one,
and the one that works is the one the lock will not allow.

## Consequences

- We keep Ragas (`eval/run_ragas.py`) for faithfulness, context precision and context
  recall. It resolves cleanly, moves neither langchain (0.3.30) nor torch (2.11.0), and
  leaves `requirements.lock` untouched.
- We have **no distributed tracing backend**. That is a real gap, and it is partly
  covered from the other direction: F23 records the full pipeline trace per answer, F24
  verifies each claim against its source, and `scripts/simulate.py` diffs what the model
  saw across retrieval configs. Those answer "what did the model receive and did it use
  it" for a single answer; they do not aggregate across runs or across time.
- Revisit if Phoenix stops registering a pytest plugin by default, or if a version that
  declares its dependencies correctly becomes resolvable here. Langfuse (MIT,
  self-hostable, OpenTelemetry-based) is the other candidate from the same research and
  was not evaluated — it is the obvious next thing to try.
