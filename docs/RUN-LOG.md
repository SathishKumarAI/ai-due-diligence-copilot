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

## Eval harness (F10) — first execution

It had never run: `python eval/run_eval.py` puts `eval/` on `sys.path`, not the repo
root, so `import app` raised `ModuleNotFoundError` on line 1. That is the invocation in
both the docstring and the `eval:` Makefile target. Fixed, along with the harness
building its engine with no retriever and no reranker (it now goes through
`app.main.build_engine`) and a judge parser where `"GROUNDED" in verdict` also matched
`"NOT GROUNDED"`.

```
provider=ollama model=llama3.1:8b retrieval=hybrid rerank=False top_k=5

Retrieval hit-rate : 100%  (threshold 70%)
Faithfulness       :  80%  (threshold 70%)
PASS      10 questions, 28.6s, exit 0
```

**Read the hit-rate as vacuous, not good.** The corpus is 4 chunks and `top_k` is 5, so
retrieval returns the entire corpus for every question and the metric cannot discriminate.
It means something only against a real corpus.

## Corpus fetch (F22) — blocked on a contact address

`scripts/fetch_corpus.py` 403s on every ticker, then printed `Done. 0 new document(s)`
and exited 0. Measured, with the original UA repeated to rule out rate-limiting:

| User-Agent | Result |
|---|---|
| `rag-learning-companion (github.com/SathishKumarAI)` | **403** (×2) |
| `rag-learning-companion SathishKumarAI@users.noreply.github.com` | **403** |
| `RAG Learning Companion SathishKumarAI@users.noreply.github.com` | **403** |
| `rag-learning-companion acme@example.com` | 200 |
| `RAG Learning Companion acme@example.com` | 200 |

SEC requires a deliverable contact email, so the handle-only default could never work —
and it blocks `users.noreply.github.com`, the very identity this project adopted to keep
contact details out of the repos. The script now requires `SEC_USER_AGENT` and exits 2
with instructions rather than failing silently. **Setting a real address is the repo
owner's call, so no corpus is indexed yet and no meaningful baseline exists.**

## Web UI (F14, F18, F19, F23) — first execution

`web/node_modules` was a Linux install and had to be reinstalled. `tsc --noEmit` and
`next build` both pass clean (3 routes). Then the UI turned out never to have rendered
an answer at all.

**The chat was dead.** Clicking any question left the caret blinking forever, while the
POST to `/v1/ask/stream` returned 200 and the server finished streaming in 7.8s.
`sse-starlette` terminates lines with CRLF, so frames arrive separated by `\r\n\r\n`:

```
e v e n t :   t o k e n \r \n d a t a :   T h e \r \n \r \n
```

`web/lib/api.ts` split frames on `"\n\n"`, which never matched. Everything accumulated
in the buffer; the end-of-stream flush passed the whole response to `handleFrame` as one
frame; `JSON.parse` threw; and `catch { /* ignore malformed trailing frame */ }`
swallowed it. A total failure with 200 on the wire and a clean console. Because the F23
inspector hangs off the answer bubble, **the feature the README leads with was
unreachable.** Fixed by normalising CRLF on the buffer.

Verified in Chrome against API :8000 + the production Next build on :3000:

| Path | Result |
|---|---|
| Ask (streaming) | renders "ARR is $12.4M, up from $8.9M … 39% YoY growth" with a `[1]` chip |
| Sources panel | `acme_robotics_pitch.md` with snippet |
| **F23 inspector** | stage strip, 10 token chips, 4 chunks with distances, prompt accordion (3032 ctx chars), retrieve 15.8ms / generate 2588.3ms |
| F19 follow-up | "And how does that compare to the prior year?" — condense resolved "that" and answered from history |
| F19 feedback | thumbs-up persisted to `data/feedback.jsonl` |
| F18 + F20 upload | scanned PDF (no text layer) → OCR → indexed → later cited: *"Gross margin is 61 percent [1]"* |
| F15 What's New | live GitHub release rendered |
| OCR probe | `ocr_available() True`; both the image and the `pdf2image`/Poppler path work — the MiKTeX-supplied Poppler is fine |

## Open, found by running — not yet fixed

- **A refusal still returns 4 citations.** The answer says the documents do not cover the
  question, and the response carries every retrieved chunk as a source. `_citations`
  (`app/rag.py:128`) falls back to *all* retrieved docs when the answer has no `[n]` markers.
  It is deliberate and asserted by `tests/test_citations.py`, so it needs a decision rather
  than a quiet change — but shipping four source cards under "the documents do not cover
  this" inverts the product's core promise.
- **No real corpus yet**, and it needs a decision rather than code: export
  `SEC_USER_AGENT="Name email@domain"` with an address you are willing to publish in
  request headers, then `python scripts/fetch_corpus.py && python -m app.ingest`.
- **`eval/` and `scripts/` are outside the lint gate.** CI runs `ruff check app tests`
  only, so neither the harness nor the fetchers were ever linted or type-checked — both
  files shipped with defects that a gate covering them would likely have caught.
- **`web/` has no test runner at all.** The SSE parser above is exactly the logic that
  should have one. Adding a runner is a dependency decision (CLAUDE.md: don't add
  dependencies without asking), so it is flagged rather than done.
- **`/ready` can report `ready: true` with `indexed_chunks: -1`.** Re-ingesting while the
  API is serving leaves it holding a stale Chroma handle; the bare `except` returns the
  `-1` sentinel and readiness still says healthy. Restarting the API restores `4`. A
  readiness probe that cannot see its collection arguably should not report ready.
- **Release notes render as literal markdown** on What's New (`**bold**` shows asterisks).
  `AnswerText.tsx` states the no-markdown-library policy explicitly, so this is that
  policy meeting markdown-authored release notes — a decision, not an oversight.
- **No lockfile.** Every drift above traces back to range-pinned requirements. Until there is
  a lockfile, a green gate today says nothing about tomorrow.
- **MED and ENG need `scripts/sync_engine.py`** — engine files changed here, so their
  `test_parity` will fail until synced. `scripts/setup.*` and `Dockerfile.gpu` are *not*
  manifest-tracked and must be copied across by hand.
