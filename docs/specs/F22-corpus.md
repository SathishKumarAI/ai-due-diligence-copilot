# Feature Spec — F22 Open-access corpus fetch

## Summary
A stdlib-only script that fetches a real, redistributable finance corpus — recent 10-K
annual reports from SEC EDGAR — so the RAG runs against genuine due-diligence documents
instead of only synthetic samples.

## Problem / why
Demos and evals are more convincing on real filings, but the repo is public, so the corpus
must be freely redistributable. SEC filings are public records; books and other copyrighted
material are excluded. The fetch has to be safe to run in CI (offline-tolerant) and safe to
re-run.

## Users & context
A developer/operator prep step, not part of the request path. Populates `data/corpus/`;
`python -m app.ingest` then (re)builds the index over it.

## Behaviour (acceptance criteria)
- WHEN `scripts/fetch_corpus.py` runs THEN for each configured company it resolves the most
  recent **10-K** primary document via the EDGAR submissions API and downloads it as
  `data/corpus/<ticker>_10k.txt`.
- WHEN a target file already exists THEN it is skipped (idempotent — re-run adds only new companies).
- WHEN `--dry-run` is passed THEN it prints the URLs it would fetch and downloads nothing.
- WHEN `--limit N` is passed THEN only the first N companies are considered.
- WHEN a network/IO error occurs THEN it is logged as `WARN` and skipped, never fatal (CI-friendly / offline-safe).
- WHEN a document is saved THEN it is recorded in `data/SOURCES.md` with its source URL (deduped).

## Rules / logic
- `app`-free, **stdlib only** (`urllib`, `json`, `re`, `html`) — no added dependency.
- `latest_10k_url(cik)` reads `https://data.sec.gov/submissions/CIK<cik>.json`, walks the
  parallel `form` / `accessionNumber` / `primaryDocument` arrays, and builds the Archives URL
  for the first `10-K`.
- `_html_to_text` strips script/style then tags, unescapes entities, and collapses whitespace.
- **Polite / rate-limited**: sends the SEC-required descriptive `User-Agent` (from
  `SEC_USER_AGENT`, defaulting to a public GitHub handle — no personal contact in the repo)
  and sleeps `RATE_LIMIT_SECONDS` (0.5s) between requests, well under SEC's 10 req/s.
- **Provenance**: `record_source` appends a `- **<ticker> 10-K** (SEC EDGAR, public record): <url>`
  line to `data/SOURCES.md`, creating the file with a header on first write.
- Company set (`COMPANIES`): AAPL, MSFT, AMZN, GOOGL, NVDA by CIK.

## Config / env knobs
- `SEC_USER_AGENT` — descriptive UA per SEC guidance (a GitHub URL is fine).
- CLI: `--limit N`, `--dry-run`.

## Out of scope (for now)
- Books and any copyrighted corpus (deliberately excluded for redistributability).
- Full-text-search of all filing types — 10-K primary documents only.
- Sibling repos supply their **own** domain sources: healthcare uses PubMed Central Open
  Access + WHO/CDC; engineering uses arXiv `cs.*` + public RFCs. Only the source list differs;
  the stdlib-only, idempotent, rate-limited, provenance-recording shape is shared.

## Data touched
- Reads: SEC EDGAR (public). Writes: `data/corpus/<ticker>_10k.txt`, `data/SOURCES.md`.

## Edge cases
- Company with no 10-K on file (skipped with a message) · already-present file (skipped) ·
  duplicate URL in `SOURCES.md` (not re-appended) · unreadable/garbled HTML (best-effort
  decode with `errors="ignore"`).

## Done when
- The script fetches real 10-Ks into `data/corpus/`, is idempotent and offline-safe, records
  provenance in `data/SOURCES.md`, and ships no copyrighted content — verified by a `--dry-run`
  that lists URLs and a re-run that skips existing files.
