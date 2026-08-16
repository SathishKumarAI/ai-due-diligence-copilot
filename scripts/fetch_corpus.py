#!/usr/bin/env python3
"""Fetch a real, open corpus for the finance domain (feature F22).

Source: **SEC EDGAR** — U.S. public-company filings. Filings are public records and
freely redistributable, so this corpus is safe to ship in a public repo (unlike books,
which are excluded for copyright). We pull each company's most recent **10-K** annual
report via the official EDGAR submissions API.

Design:
- **stdlib only** (urllib) — no extra dependency, runs anywhere.
- **Idempotent** — skips files already present; re-run to add new companies only.
- **Polite** — sends the SEC-required descriptive User-Agent and rate-limits requests.
- **Offline-safe** — a single ticker's network error is logged and skipped, never fatal;
  fetching *nothing at all* does exit non-zero, so a dead run cannot read as success.
- **Provenance** — every download is recorded in ``data/SOURCES.md`` with its URL.

Usage:
    python scripts/fetch_corpus.py                 # fetch defaults into data/corpus/
    python scripts/fetch_corpus.py --limit 3       # first 3 companies only
    python scripts/fetch_corpus.py --dry-run       # list what would be fetched

SEC_USER_AGENT is **required** — SEC 403s any request without a contact email, and a
GitHub URL or noreply address is not accepted (see the measurements below):
    SEC_USER_AGENT="Jane Roe jane@example.com" python scripts/fetch_corpus.py
"""

from __future__ import annotations

import argparse
import html
import json
import os
import re
import sys
import time
import urllib.error
import urllib.request
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
CORPUS_DIR = PROJECT_ROOT / "data" / "corpus"
SOURCES_FILE = PROJECT_ROOT / "data" / "SOURCES.md"

# SEC requires a User-Agent carrying a real contact address, in "Name email@domain"
# form, and rejects anything else with a blanket 403. Measured against
# data.sec.gov/submissions/CIK0000320193.json on 2026-08-16:
#
#   rag-learning-companion (github.com/SathishKumarAI)                    403
#   rag-learning-companion SathishKumarAI@users.noreply.github.com        403
#   RAG Learning Companion SathishKumarAI@users.noreply.github.com        403
#   rag-learning-companion acme@example.com                               200
#   RAG Learning Companion acme@example.com                               200
#
# So an email is mandatory (the handle-only default could never have worked), and
# GitHub's users.noreply.github.com domain is blocked outright — which is why this
# cannot simply reuse the repo's git identity. Deliberately left unset: no contact
# address is committed to this repo. Export SEC_USER_AGENT to supply your own.
USER_AGENT = os.environ.get("SEC_USER_AGENT", "")

USER_AGENT_HELP = """SEC_USER_AGENT is not set.

SEC EDGAR rejects requests without a contact email and returns 403 for every fetch.
Set a User-Agent of the form "Your Name your-email@domain":

    export SEC_USER_AGENT="Jane Roe jane@example.com"      # bash
    $env:SEC_USER_AGENT = "Jane Roe jane@example.com"      # PowerShell

Note: users.noreply.github.com addresses are blocked by SEC - use a deliverable one.
No contact address is stored in this repo, which is why this must come from the
environment. See docs/INGESTION.md."""
RATE_LIMIT_SECONDS = 0.5  # SEC allows up to 10 req/s; stay well under.

# A small set of well-known public companies (CIK, ticker). 10-Ks are the classic
# due-diligence document, so they exercise the finance RAG well.
COMPANIES: list[tuple[str, str]] = [
    ("0000320193", "AAPL"),  # Apple
    ("0000789019", "MSFT"),  # Microsoft
    ("0001018724", "AMZN"),  # Amazon
    ("0001652044", "GOOGL"),  # Alphabet
    ("0001045810", "NVDA"),  # NVIDIA
]

_TAG_RE = re.compile(r"<[^>]+>")
_SCRIPT_STYLE_RE = re.compile(r"<(script|style)[^>]*>.*?</\1>", re.DOTALL | re.IGNORECASE)
_WS_RE = re.compile(r"[ \t]{2,}")
_NL_RE = re.compile(r"\n{3,}")


def _get(url: str) -> bytes:
    req = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
    with urllib.request.urlopen(req, timeout=30) as resp:  # noqa: S310 - fixed SEC host
        return resp.read()


def _html_to_text(raw: bytes) -> str:
    text = raw.decode("utf-8", errors="ignore")
    text = _SCRIPT_STYLE_RE.sub(" ", text)
    text = _TAG_RE.sub(" ", text)
    text = html.unescape(text)
    text = _WS_RE.sub(" ", text)
    text = "\n".join(line.strip() for line in text.splitlines())
    return _NL_RE.sub("\n\n", text).strip()


def latest_10k_url(cik: str) -> str | None:
    """Return the URL of a company's most recent 10-K primary document, or None."""
    meta = json.loads(_get(f"https://data.sec.gov/submissions/CIK{cik}.json"))
    recent = meta.get("filings", {}).get("recent", {})
    forms = recent.get("form", [])
    accessions = recent.get("accessionNumber", [])
    primaries = recent.get("primaryDocument", [])
    for form, accession, primary in zip(forms, accessions, primaries, strict=False):
        if form == "10-K" and primary:
            acc = accession.replace("-", "")
            cik_int = int(cik)
            return f"https://www.sec.gov/Archives/edgar/data/{cik_int}/{acc}/{primary}"
    return None


def record_source(ticker: str, url: str) -> None:
    SOURCES_FILE.parent.mkdir(parents=True, exist_ok=True)
    header = "# Corpus sources\n\nOpen, redistributable documents fetched by `scripts/fetch_corpus.py`.\n\n"
    if not SOURCES_FILE.exists():
        SOURCES_FILE.write_text(header, encoding="utf-8")
    line = f"- **{ticker} 10-K** (SEC EDGAR, public record): {url}\n"
    existing = SOURCES_FILE.read_text(encoding="utf-8")
    if url not in existing:
        SOURCES_FILE.write_text(existing + line, encoding="utf-8")


def fetch(limit: int | None, dry_run: bool) -> int:
    CORPUS_DIR.mkdir(parents=True, exist_ok=True)
    companies = COMPANIES[:limit] if limit else COMPANIES
    saved = 0
    for cik, ticker in companies:
        dest = CORPUS_DIR / f"{ticker.lower()}_10k.txt"
        if dest.exists():
            print(f"skip {ticker}: already present")
            continue
        try:
            url = latest_10k_url(cik)
            time.sleep(RATE_LIMIT_SECONDS)
            if not url:
                print(f"skip {ticker}: no 10-K found")
                continue
            if dry_run:
                print(f"would fetch {ticker}: {url}")
                continue
            text = _html_to_text(_get(url))
            time.sleep(RATE_LIMIT_SECONDS)
            dest.write_text(text, encoding="utf-8")
            record_source(ticker, url)
            saved += 1
            print(f"saved {ticker}: {len(text):,} chars -> {dest.relative_to(PROJECT_ROOT)}")
        except (urllib.error.URLError, TimeoutError, OSError) as exc:
            print(f"WARN {ticker}: fetch failed ({exc}); skipping")
    return saved


def main() -> int:
    ap = argparse.ArgumentParser(description="Fetch open finance corpus (SEC EDGAR 10-Ks).")
    ap.add_argument("--limit", type=int, default=None, help="max companies to fetch")
    ap.add_argument("--dry-run", action="store_true", help="list URLs, download nothing")
    args = ap.parse_args()

    # Fail before the first request rather than after five identical 403 warnings.
    if not USER_AGENT.strip():
        print(USER_AGENT_HELP, file=sys.stderr)
        return 2

    n = fetch(args.limit, args.dry_run)
    if args.dry_run:
        return 0

    print(f"\nDone. {n} new document(s) in {CORPUS_DIR.relative_to(PROJECT_ROOT)}.")
    if n == 0:
        # Previously this path printed "Done." and exited 0, so a corpus fetch that
        # downloaded nothing at all looked like a success to a caller or a CI step.
        print(
            "\nNo documents were fetched. If every ticker logged a 403, SEC rejected "
            f"SEC_USER_AGENT={USER_AGENT!r} — it must carry a deliverable contact email.",
            file=sys.stderr,
        )
        return 1
    print("Next: python -m app.ingest  (re)builds the index over the new corpus.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
