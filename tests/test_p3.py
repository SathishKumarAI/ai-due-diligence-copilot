"""Offline tests for P3 features: OCR (F20), cleaning (F21), trace (F23).

No Tesseract, no network — OCR helpers are exercised only on their import-safe paths.
"""

from __future__ import annotations

from pathlib import Path

from langchain_core.documents import Document

from app import ocr
from app.cleaning import (
    CleaningConfig,
    clean_documents,
    clean_text,
    dedupe_chunks,
)
from app.trace import chunk_traces, dense_scores, tokenize_trace


# --- F21 cleaning ---------------------------------------------------------------


def test_clean_text_collapses_and_joins():
    raw = "inter-\nnational   spacing\n\n\n\nlines\n42\n"
    out, report = clean_text(raw)
    assert "international" in out  # hyphenated line-break joined
    assert "   " not in out  # runs of spaces collapsed
    assert "\n42\n" not in out  # bare page-number line dropped
    assert report.chars_after <= report.chars_before
    assert "normalize_unicode(NFKC)" in report.steps


def test_clean_text_can_disable_steps():
    cfg = CleaningConfig(drop_page_number_lines=False)
    out, _ = clean_text("body\n7\nmore", cfg)
    assert "7" in out


def test_clean_documents_strips_running_headers():
    pages = [
        Document(page_content=f"ACME CONFIDENTIAL\nPage body {i}\nFooter X", metadata={"source": "a.pdf", "page": i})
        for i in range(1, 6)
    ]
    cleaned = clean_documents(pages)
    assert all("ACME CONFIDENTIAL" not in d.page_content for d in cleaned)
    assert all("Footer X" not in d.page_content for d in cleaned)
    assert any("Page body" in d.page_content for d in cleaned)
    assert all(d.metadata.get("cleaned") for d in cleaned)


def test_dedupe_chunks_drops_near_duplicates():
    a = Document(page_content="the quick brown fox jumps over the lazy dog again")
    b = Document(page_content="the quick brown fox jumps over the lazy dog again!")
    c = Document(page_content="completely different content about revenue and growth metrics")
    kept = dedupe_chunks([a, b, c], threshold=0.9)
    assert len(kept) == 2  # b is a near-duplicate of a


# --- F20 OCR (import-safe paths only) -------------------------------------------


def test_ocr_available_returns_bool():
    assert isinstance(ocr.ocr_available(), bool)


def test_load_with_ocr_rejects_unsupported_suffix():
    import pytest

    with pytest.raises(ValueError):
        ocr.load_with_ocr(Path("notes.txt"))


def test_pdf_needs_ocr_on_bad_path_assumes_scanned():
    # Unreadable file -> treat as scanned (True) rather than crash.
    assert ocr.pdf_needs_ocr(Path("/nonexistent/file.pdf")) is True


def test_image_suffixes_cover_common_formats():
    assert {".png", ".jpg", ".tiff"} <= set(ocr.IMAGE_SUFFIXES)


# --- F23 trace ------------------------------------------------------------------


def test_tokenize_trace_counts():
    tr = tokenize_trace("Revenue grew 40% year over year")
    assert tr.token_count == len(tr.tokens)
    assert "40%" in tr.tokens  # figure kept whole by the lexical tokenizer
    assert tr.char_count == len("Revenue grew 40% year over year")


def test_chunk_traces_attaches_scores():
    docs = [Document(page_content="hello world", metadata={"source": "x.md", "page": 2})]
    from app.retrieval import _doc_key

    score_map = {_doc_key(docs[0]): 0.87}
    rows = chunk_traces(docs, score_map)
    assert rows[0].rank == 1
    assert rows[0].dense_score == 0.87
    assert rows[0].extraction_method == "text"


def test_dense_scores_graceful_on_fake_store(fake_store):
    scores = dense_scores(fake_store, "concentration risk", k=3)
    assert isinstance(scores, dict)  # real Chroma returns scores; shape is a map


def test_answer_with_trace_populates_pipeline(fake_engine):
    answer, trace = fake_engine.answer_with_trace("What is the concentration risk?")
    assert answer.answer
    assert trace.original_question == "What is the concentration risk?"
    assert trace.retrieval_mode in {"dense", "hybrid"}
    assert trace.tokenization.token_count > 0
    assert trace.retrieved  # got chunks
    assert trace.system_prompt  # exact prompt captured
    assert "Context passages" in trace.user_prompt
