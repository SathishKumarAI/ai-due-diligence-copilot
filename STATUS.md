# STATUS — ai-due-diligence-copilot (FIN)

**Last touched:** 2026-08-17 · **Branch:** `fix/docker-base-cves` · **Tree:** clean

This is the **reference repo** of three siblings. Engine changes are made here and pushed
outward with `scripts/sync_engine.py`. MED (`healthcare-knowledge-navigator`) and ENG
(`engineering-intelligence-hub`) both have their catch-up PR open and passing `quality`
for the first time; see "Next action".

## Where it stopped (2026-08-17)

**PR #20 is merged** (`0fdd77f`) — the provider seam now has two independent halves and an
OpenAI-compatible adapter. All three CI jobs green.

**PR [#21](https://github.com/SathishKumarAI/ai-due-diligence-copilot/pull/21) is open and
rebuilding:** `apt-get upgrade` in the Dockerfile runtime stage. This repo's `docker` job
passed today and **would have failed on the next push** — the siblings hit 9 HIGH findings
on the identical base image minutes later, all `CVE-2026-53615` in Debian's `util-linux`.
The only difference was Trivy's database updating in between. Measured with CI's own Trivy
version and flags: 9 findings / exit 1 → **0 findings / exit 0**.

Local gate on the merged tree:

```
pytest                140 passed        (was 119; 21 new provider tests)
ruff check            All checks passed!
ruff format --check   35 files already formatted
mypy app              Success: no issues found in 19 source files
npm test (web)        5 passed
python -m app.ingest  4 documents, 11 chunks -> due_diligence_182f5fd57187
```

Real query, `ollama`/`llama3.1:8b` + `bge-small`, `LOCAL_ONLY=true`:
*"What is the pre-money valuation in the term sheet?"* →
*"The pre-money valuation is $180,000,000 [2]."* citing `acme_term_sheet.md`.

### What #20 changed

`PROVIDER` welded the generator to the embedder. `LLM_PROVIDER` and `EMBED_PROVIDER` now
pick each half, both defaulting to `PROVIDER`, so every existing `.env` is untouched. The
new `openai` provider is one adapter for everything speaking that wire format — OpenAI,
Groq, Together, DeepSeek, vLLM, TGI, LM Studio — selected by `OPENAI_BASE_URL`. `LOCAL_ONLY`
is now judged per half and **by endpoint**, so `openai` pointed at localhost is correctly
treated as local.

It also fixed a silent corruption: `collection_name` was the constant `"due_diligence"`, so
changing `HF_EMBED_MODEL` reopened the *previous* model's collection. At a different
dimensionality Chroma raises; **at the same dimensionality it does not**, and answers come
from vectors the current model never made. `docs/specs/F04` had carried "switching provider
invalidates the index → re-ingest" as an operator instruction since v0.1.0 and nothing
enforced it. Now keyed on the embedding half.

## The earlier ship (2026-08-16)

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

In order:

1. **Merge PR #21** when green.
2. **Sync the provider work into MED and ENG.** `python scripts/sync_engine.py --to
   ../healthcare-knowledge-navigator ../engineering-intelligence-hub`, **plus a hand-copy**
   of three things the manifest does not track: the provider block in `app/config.py`
   (~83 lines), `tests/test_providers.py`, and the `langchain-openai` line in
   `requirements.txt`. The engine now *imports* `ProviderName` and `LOCAL_HOSTS` from
   `app/config.py`, so a sync without the config block will not import. Then relock and
   regenerate the manifest.
3. **`chunk_size` 1000 → 400 in MED and ENG.** User approved 2026-08-17. The numbers are in
   the umbrella `../STATUS.md` — **do not reuse this repo's justification**, the sibling
   hit@1 does not improve and ENG's gets marginally worse. Ship it for citation precision:
   at 1000 each document is one chunk, so `app/grounding.py:240` verifies a claim against
   an entire document's token set.
4. **Training track** (fine-tune embedder + cross-encoder). Architectural — design doc
   before code. Needs the RTX host and a corpus worth training on.
5. **Get a real corpus in.** Almost every remaining limitation is downstream of a 4-document
   synthetic sample. Blocked on one env var: `SEC_USER_AGENT` needs a deliverable contact
   email (SEC EDGAR rejects `users.noreply.github.com`, measured in `docs/INGESTION.md`).
6. **Grow the eval set.** `scripts/generate_testset.py` produces synthesis and multi-hop
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

- **The manifest defect from #16 was in MED and ENG, and is now fixed there** (2026-08-17).
  Both held 2457 CR across `app/*.py` and all 12 manifest entries were wrong. Fixed by
  refreshing each tree through `.gitattributes` (`git rm --cached -r . && git reset --hard`,
  no content change) and copying this repo's `sync_engine.py`, whose generator now writes the
  manifest with `newline="\n"`. If it reappears, that is the recipe.
- **A green Trivy run is not a Trivy run that stays green.** This repo's `docker` job passed
  and the siblings failed on the identical base image minutes later, purely because Trivy's
  DB updated. The Dockerfile now runs `apt-get upgrade` in the runtime stage — the gate uses
  `ignore-unfixed`, so it blocks only on findings that *have* a patch, and suppressing one in
  `.trivyignore` would defeat the point of that file.
- **`requirements.lock` is what ships.** Editing `requirements.txt` alone changes nothing in
  the image. Run `scripts/lock.sh` (needs `uv`) — and it must stay `--universal`.
- **`app/config.py` and `app/prompts.py` are NOT in the engine manifest** — deliberately, they
  are per-domain. This trap fired for real on 2026-08-17: the engine now *imports*
  `ProviderName` and `LOCAL_HOSTS` from `app/config.py`, so syncing `app/*.py` without the
  config block will not even import. After any sync, grep for settings and symbols the new
  engine code reads.
- **The same gap silently stalls measured fixes in this repo.** `chunk_size` moved 1000 → 400
  here in PR #12 and never reached the siblings, because `config.py` is never synced. Both are
  still at 1000. Whenever a fix lands in `config.py`, it reaches MED and ENG only by hand.
- **`scripts/setup.*`, `Dockerfile*`, `scripts/lock.*`, `scripts/sync_engine.py`, the
  lockfiles and `.github/workflows/ci.yml` are not manifest-tracked**, so `test_parity` will
  not catch drift in them. Copy by hand. **`ci.yml` embeds the repo name** in the
  `docker build` tag and the Trivy `image-ref` — a blind copy retags a sibling's image as this
  one's.
- **Chroma teardown locks files on Windows.** Wrapping a `PersistentClient` in a
  `TemporaryDirectory` raises `PermissionError` on cleanup. Embed and rank in memory when
  measuring retrieval.
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
