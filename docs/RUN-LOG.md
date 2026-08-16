# RUN-LOG — first real execution

**2026-08-16 · Windows 11 · RTX 5070 Ti (16 GB, driver 610.47) · Python 3.12.10**

Every prior entry in `BACKLOG.md` was verified by review and by offline fakes. `BACKLOG.md`
recorded one blocked item — *"Full app run + eval on the Windows/RTX host"* — because the
build machine had a hard no-local-execution rule. This is the log of that run finally
happening. Commands and their real output, pass or fail.

## Environment

```
Python 3.12.10 · uv 0.11.32 · node 24.18.1 · Docker 29.6.2 · git 2.55.0
Ollama serving on :11434 · Tesseract 5.4.0 · NVIDIA GeForce RTX 5070 Ti, 16303 MiB
```

## What blocked the run, in the order it was hit

### 1. torch built for the wrong GPU generation

`scripts/setup.ps1` pinned the **cu124** wheel index and `Dockerfile.gpu` a CUDA 12.4 base.
The 5070 Ti is Blackwell — compute capability `sm_120` — and cu124 ships kernels only through
`sm_90`. torch imports fine and then fails at the first CUDA op. Fixed to cu128:

```
torch 2.11.0+cu128 · cuda build 12.8 · available True
device NVIDIA GeForce RTX 5070 Ti · capability (12, 0)
arch list ['sm_75', 'sm_80', 'sm_86', 'sm_90', 'sm_100', 'sm_120']
matmul ok True
```

### 2. A venv from the other platform

The repo carried a 632 MB Linux `.venv` (`home = /home/deva/...`, `bin/` not `Scripts/`) and a
363 MB Linux `web/node_modules`. `python -m venv` does not repair a foreign venv, so
`setup.ps1` died on the activate line with a misleading "file not found". Both removed; both
setup scripts now fail with a message naming the real cause.

### 3. The quality gate had never passed — CI was red from day one

`gh run list` shows **failure on all 7 runs since the first commit (2026-06-24)**. CI dies at
`ruff check`, step one of four, so **mypy and pytest have never run in CI at all**. That is how
two broken tests and six type errors survived under a ✅ for F13. Root cause of the drift:
range-pinned requirements with no lockfile, so today's ruff/numpy/langchain are not July's.
See the `fix: make the quality gate pass for the first time` commit for the six defects.

### 4. F07 embedding cache could never write a key

The first ingest died before a single vector:

```
InvalidKeyException: Invalid characters in key:
ollama:BAAI/bge-small-en-v1.5:voyage-3.5ee0960b8-396a-5bb4-9edf-a776e9d398fb
```

The namespace was `{provider}:{hf_model}:{voyage_model}`; `LocalFileStore` validates the
key against `^[a-zA-Z0-9_.\-/]+$` and the colons fail it. Guaranteed on the documented quick
start of all three repos, for a feature marked done in all three.

## The run

```
$ python -m app.ingest
Ingested 4 documents into 4 chunks (collection: due_diligence).       exit 0, 7.4s

$ curl -s localhost:8000/health
{"status":"ok","app":"AI Due Diligence Copilot","version":"0.1.0","provider":"ollama"}

$ curl -s localhost:8000/ready
{"ready":true,"indexed_chunks":4}

$ curl -s localhost:8000/v1/sources
4 sources, 1 chunk each, total_chunks 4
```

**Grounded answer with citations** — `/v1/ask`, "What are the main risk factors?":

```
provider  : ollama
timings   : retrieve_ms 216.3 · generate_ms 13302.8
citations : acme_risk_factors.md, acme_robotics_pitch.md, acme_10k_excerpt.md
answer    : The main risk factors for Acme Robotics are:
            * Customer concentration: A single customer accounts for 22% of ARR [1]
            * Supply chain disruption: key actuators from a single overseas supplier [1]
            * Competition: two larger incumbents with deeper balance sheets [1]
            * Regulatory: CE machinery safety certification not yet started [1]
```

**F23 trace** — `explain=true`, "What is the ARR and growth rate?":

```
mode      : hybrid | rerank: False
tokens    : ['what','is','the','arr','and','growth','rate']
retrieved : 1 acme_risk_factors.md 0.797 · 2 acme_robotics_pitch.md 0.924
            3 acme_10k_excerpt.md 0.874 · 4 acme_term_sheet.md 0.881
ctx chars : 3032 | retrieve_ms 8.6 · generate_ms 2528.6
answer    : The Annual Recurring Revenue (ARR) is $12.4M [2]. Revenue grew 39% YoY [2].
```

`retrieve_ms` 216.3 cold → 8.6 warm: the embedding cache is doing its job for the first time.

**Refusal path** — asked something the corpus cannot answer:

```
Q: What was Tesla Q3 2025 vehicle delivery count?
A: The provided documents do not cover this. There is no mention of Tesla or its
   vehicle delivery counts in any of the passages.
```

**SSE streaming** — `/v1/ask/stream` emits `event: token` frames correctly. Never previously
exercised by any test.

**Offline suite on this interpreter:** `64 passed, 1 warning in 4.35s`, exit 0.
Gate: `ruff check` clean · `ruff format --check` clean · `mypy app` clean · `pytest` exit 0.

## Open, found by running — not yet fixed

- **A refusal still returns 4 citations.** The answer says the documents do not cover the
  question, and the response carries every retrieved chunk as a source. `_citations`
  (`app/rag.py:128`) falls back to *all* retrieved docs when the answer has no `[n]` markers.
  It is deliberate and asserted by `tests/test_citations.py`, so it needs a decision rather
  than a quiet change — but shipping four source cards under "the documents do not cover
  this" inverts the product's core promise.
- **The eval harness does not measure the shipped system.** `eval/run_eval.py:41` builds the
  engine with no retriever and no reranker, so it silently scores pure dense retrieval no
  matter what `RETRIEVAL_MODE=hybrid` says. Any number it produces today describes a system
  nobody ships. Fix before recording a baseline.
- **No real corpus yet.** `data/` is still the 4 synthetic Acme files; `scripts/fetch_corpus.py`
  (SEC EDGAR) has never been run, so there is no `data/corpus/` and no `data/SOURCES.md`.
- **No lockfile.** Every drift above traces back to range-pinned requirements. Until there is
  a lockfile, a green gate today says nothing about tomorrow.
- **MED and ENG need `scripts/sync_engine.py`** — engine files changed here, so their
  `test_parity` will fail until synced. `scripts/setup.*` and `Dockerfile.gpu` are *not*
  manifest-tracked and must be copied across by hand.
