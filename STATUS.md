# STATUS — ai-due-diligence-copilot (FIN)

**Last touched:** 2026-08-16 · **Branch:** `main` · **Tree:** clean

This is the **reference repo** of three siblings. Engine changes are made here and pushed
outward with `scripts/sync_engine.py`. MED (`healthcare-knowledge-navigator`) and ENG
(`engineering-intelligence-hub`) are in sync as of today — but **neither has been pushed**;
see "Next action".

## Where it stopped

**Everything is on `origin/main`, and CI is green there for the first time.** The 40 commits
that had never left this disk shipped as 18 reviewed PRs (#1–#18), squash-merged in
dependency order. `main` is byte-identical to the tree that passed CI.

```
run 2ba7c34 on main    quality: success   web: success   docker: success
```

That is the first fully green run in this repo's history. Prior to today CI had failed on
**all 7 runs since 2026-06-24**, always at `ruff check`, step one of four — so `mypy` and
`pytest` had never executed in CI at all, and the `docker` job (gated behind `quality`) had
**never run once**.

Local gate, on the same tree:

```
ruff format --check   104 files already formatted
ruff check            All checks passed!   (app tests eval scripts)
mypy app              Success: no issues found in 19 source files
pytest                119 passed
tsc --noEmit          exit 0
vitest run            5 passed
```

## Next action

Pick one:

1. **Ship MED and ENG.** Each has 3 unpushed commits on `chore/sync-from-fin-2026-08` plus
   an unpushed `rag-p3`, and `main` on both is still at the pre-sync commit. They are now the
   only copies of that work on one disk — the risk FIN just retired.
   **They almost certainly carry the same manifest defect fixed in #16** (see Traps).
2. **Get a real corpus in.** Almost every remaining limitation is downstream of a 4-document
   synthetic sample. Blocked on one env var: `SEC_USER_AGENT` needs a deliverable contact
   email (SEC EDGAR rejects `users.noreply.github.com`, measured in `docs/INGESTION.md`).
3. **Grow the eval set.** `scripts/generate_testset.py` produces synthesis and multi-hop
   questions the hand-written set does not have. It already found the failure mode the
   hand-written set is blind to.

## What shipping it found

Three defects that were invisible locally and only CI could see. All three are fixed and
merged; they are recorded because each one is a class of mistake, not a one-off.

- **The engine manifest held CRLF hashes** (#16). The blobs are LF and always were; this
  *working tree* was cloned before `.gitattributes` existed, and Git never renormalises an
  existing checkout. `ENGINE_MANIFEST.sha256` hashes files from disk, so it recorded the CRLF
  rendering — passing here and failing on every Linux checkout. All 12 entries were wrong.
- **The lockfile freshness check could never pass** (#17). `uv pip compile` resolves for the
  platform it runs on, so a Windows-authored lock omits `triton`, `uvloop` and every
  `nvidia-*` wheel; CI recompiled on Linux and got 39 extra packages. It also diffed headers
  recording the `-o` path. Worse, the Linux image installed that Windows lock, so **torch's
  Linux dependencies were never pinned at all**. Now `--universal`, and CI runs
  `scripts/lock.sh` instead of restating it.
- **The Trivy action reference did not exist** (#18). `aquasecurity/trivy-action@0.28.0` —
  the releases are v-prefixed. The scan had been verified with the local `trivy` CLI, which
  checks the scan and not the reference, and the job had never run.

The common thread: **a check that has never executed is not a check**, and a check that
reimplements the thing it checks will drift from it.

## Traps

- **MED and ENG will have the manifest defect from #16** if their manifests were regenerated
  from a Windows tree. `sync_engine.py --check` will report drift that is really CRLF. Fix by
  refreshing the tree through `.gitattributes` (`git rm --cached -r . && git reset --hard`,
  no content change) and regenerating.
- **`requirements.lock` is what ships.** Editing `requirements.txt` alone changes nothing in
  the image. Run `scripts/lock.sh` (needs `uv`) — and it must stay `--universal`.
- **`app/config.py` and `app/prompts.py` are NOT in the engine manifest** — deliberately, they
  are per-domain. But a synced `main.py` reading a new setting will crash a sibling whose
  config lacks it. After any sync, grep for settings the new engine code reads.
- **`scripts/setup.*`, `Dockerfile.gpu`, the lockfiles and `.github/workflows/ci.yml` are not
  manifest-tracked**, so `test_parity` will not catch drift in them. Copy them by hand on the
  next sync — the CI and lock fixes above have not reached the siblings.
- **`pytest -q` hides the summary.** `pyproject.toml` already sets `addopts = "-q"`, so an
  extra `-q` makes it `-qq` and the pass/fail line vanishes. Use `pytest` bare.
- **Ragas scores are self-assessment** — the judge is the same llama3.1:8b that wrote the
  answers. Two runs minutes apart gave mean faithfulness 0.67 and 0.78 with no code change.
  That is why `run_ragas.py` is informational unless `--gate` is passed.
- **Never run `npm run build` while `next dev` is live** — the production build overwrites the
  dev server's `.next/`. Stop the dev server, confirm port 3000 is free, then build.
- **`data/runs.jsonl` and `eval/qa_generated.jsonl` are gitignored** — machine-local history
  and unverified LLM output respectively.

## Where to look

| Question | File |
|---|---|
| What is untrue or unmeasured about this project | `docs/LIMITATIONS.md` |
| What was measured, and when | `docs/RUN-LOG.md`, `scripts/run_history.py` |
| Why a dependency was rejected | `docs/adr/0003-*`, `docs/adr/0004-*` |
| Why an answer says what it says | `/v1/ask` with `explain=true` (F23) |
| Whether an answer is supported | `verify=true` → `app/grounding.py` (F24) |
| How the vector space looks | `docs/EMBEDDING-MAP.md` |
| Why a change was made | the PR — #1–#18 carry the reasoning and the numbers |

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
