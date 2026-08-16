# STATUS — ai-due-diligence-copilot (FIN)

**Last touched:** 2026-08-16 · **Branch:** `feat/source-diversity-cap` · **Tree:** clean

This is the **reference repo** of three siblings. Engine changes are made here and pushed
outward with `scripts/sync_engine.py`. MED (`healthcare-knowledge-navigator`) and ENG
(`engineering-intelligence-hub`) are in sync as of today.

## Where it stopped

The whole system has been run on this machine, not just read. Everything below was
verified by executing it.

```
ruff format --check   44 files already formatted
ruff check            All checks passed!
mypy app              Success: no issues found in 19 source files
pytest                113 passed
eval/run_eval.py      hit-rate 100%   faithfulness 80%     PASS
sync_engine --check   MED and ENG both in sync
docker + trivy        image builds, 0 fixable HIGH/CRITICAL
```

## Next action

**Nothing is half-done.** Pick one:

1. **Push.** ~35 commits sit on local branches; `main` is still at `61b98c1` and nothing
   has ever been pushed. This is the largest outstanding risk — all of the work below
   exists on one disk.
2. **Get a real corpus in.** Almost every remaining limitation is downstream of a
   4-document synthetic sample. Blocked on one env var: `SEC_USER_AGENT` needs a
   deliverable contact email (SEC EDGAR rejects `users.noreply.github.com`).
3. **Grow the eval set.** `scripts/generate_testset.py` produces synthesis and multi-hop
   questions the hand-written set does not have. It already found the failure mode the
   hand-written set is blind to.

## What was found by running it

None of these were visible by reading the code:

- **CI had never passed** since the first commit — it died at `ruff check`, so `mypy` and
  `pytest` had never executed in CI at all.
- **The embedding cache could never write a key**, so ingest was impossible.
- **The web chat had never rendered an answer** — SSE frames used CRLF and the parser
  split on `\n\n`. The F23 inspector was therefore unreachable.
- **Answer cache poisoning** — test fixtures' answers were being served to real users.
- **Retrieval flooding** — one uploaded document with 12 near-identical chunks took all 5
  `top_k` slots and the answer became the attacker's number, with no prompt injection.
  Capped at `MAX_CHUNKS_PER_SOURCE=2`; the same attack now returns the correct answer.
- **A serving API was permanently poisoned by `python -m app.ingest`** — it holds a dead
  Chroma handle and 500s forever. It now self-heals in ~2s.
- **The corpus generator would have deleted facts** the eval set asks about.
- **15 fixable HIGH CVEs in the shipped image**, reachable via `/v1/upload` (Pillow heap
  overflow, pypdf DoS). Bumping `requirements.txt` did nothing — the Dockerfile installs
  from `requirements.lock`.
- **A Windows clone rewrote every corpus file to CRLF**, changing chunk boundaries,
  embeddings and every content hash. Fixed with `.gitattributes`.

## Traps

- **`requirements.lock` is what ships.** Editing `requirements.txt` alone changes nothing
  in the image. Run `scripts/lock.sh` (needs `uv`).
- **`app/config.py` and `app/prompts.py` are NOT in the engine manifest** — deliberately,
  they are per-domain. But a synced `main.py` reading a new setting will crash a sibling
  whose config lacks it. That happened today. After any sync, grep for settings the new
  engine code reads.
- **`pytest -q` hides the summary.** `pyproject.toml` already sets `addopts = "-q"`, so an
  extra `-q` makes it `-qq` and the pass/fail line vanishes. Use `pytest` bare.
- **Ragas scores are self-assessment** — the judge is the same llama3.1:8b that wrote the
  answers. Two runs minutes apart gave mean faithfulness 0.67 and 0.78 with no code
  change. That is why `run_ragas.py` is informational unless `--gate` is passed.
- **`data/runs.jsonl` and `eval/qa_generated.jsonl` are gitignored** — machine-local
  history and unverified LLM output respectively.

## Where to look

| Question | File |
|---|---|
| What is untrue or unmeasured about this project | `docs/LIMITATIONS.md` |
| What was measured, and when | `docs/RUN-LOG.md`, `scripts/run_history.py` |
| Why a dependency was rejected | `docs/adr/0003-*`, `docs/adr/0004-*` |
| Why an answer says what it says | `/v1/ask` with `explain=true` (F23) |
| Whether an answer is supported | `verify=true` → `app/grounding.py` (F24) |
| How the vector space looks | `docs/EMBEDDING-MAP.md` |

## Commands

```bash
python -m app.ingest && make run          # index, then serve on :8000
cd web && npm run dev                     # UI on :3000
python eval/run_eval.py                   # hit-rate + faithfulness, records history
python eval/run_ragas.py                  # informational; --gate to block
python scripts/run_history.py --config    # trend across runs
python scripts/simulate.py --dataset      # compare retrieval configs
python scripts/sync_engine.py --check --to ../healthcare-knowledge-navigator ../engineering-intelligence-hub
```
