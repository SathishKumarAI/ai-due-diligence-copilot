"""Offline tests for the F22 corpus fetcher's pure helpers (no network)."""

from __future__ import annotations

import importlib.util
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
_spec = importlib.util.spec_from_file_location("fetch_corpus", ROOT / "scripts" / "fetch_corpus.py")
fetch_corpus = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(fetch_corpus)  # type: ignore[union-attr]


def test_html_to_text_strips_tags_and_scripts():
    raw = b"<html><style>.x{}</style><body><h1>Risk</h1><script>bad()</script><p>Revenue &amp; growth</p></body></html>"
    text = fetch_corpus._html_to_text(raw)
    assert "Risk" in text
    assert "Revenue & growth" in text  # entity unescaped
    assert "bad()" not in text  # script body removed
    assert "<" not in text  # tags gone


def test_latest_10k_url_picks_10k(monkeypatch):
    submissions = {
        "filings": {
            "recent": {
                "form": ["8-K", "10-K", "10-Q"],
                "accessionNumber": ["0000-00", "0001234567-24-000123", "0000-11"],
                "primaryDocument": ["a.htm", "aapl-10k.htm", "b.htm"],
            }
        }
    }
    monkeypatch.setattr(fetch_corpus, "_get", lambda url: json.dumps(submissions).encode())
    url = fetch_corpus.latest_10k_url("0000320193")
    assert url is not None
    assert url.endswith("/000123456724000123/aapl-10k.htm")
    assert "edgar/data/320193/" in url


def test_latest_10k_url_none_when_absent(monkeypatch):
    submissions = {
        "filings": {
            "recent": {"form": ["8-K"], "accessionNumber": ["x"], "primaryDocument": ["a.htm"]}
        }
    }
    monkeypatch.setattr(fetch_corpus, "_get", lambda url: json.dumps(submissions).encode())
    assert fetch_corpus.latest_10k_url("0000320193") is None
