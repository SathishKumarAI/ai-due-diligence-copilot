"""Text cleaning / normalization pipeline (feature F21).

Sits between *load* and *split* in ingestion:

    load (F01/F20) ─► clean (this module) ─► split ─► embed ─► Chroma

Why it exists: raw PDF/OCR text is noisy — inconsistent unicode, hyphenation at line
breaks, page numbers, and headers/footers repeated on every page. That noise pollutes
embeddings and retrieval. Cleaning is **deterministic** (no model calls) and **traceable**:
:func:`clean_text` can return a report of what changed, which the F23 introspection layer
renders so a viewer can see raw → cleaned side by side.

Everything is pure-Python (stdlib only) so it runs anywhere and is trivially unit-tested.
"""

from __future__ import annotations

import re
import unicodedata
from collections import Counter
from dataclasses import dataclass, field

from langchain_core.documents import Document

# --- regexes (module-level, compiled once) ---
_CONTROL = re.compile(r"[\x00-\x08\x0b\x0c\x0e-\x1f\x7f]")
_HYPHEN_BREAK = re.compile(r"(\w)-\n(\w)")  # "inter-\nnational" -> "international"
_TRAILING_WS = re.compile(r"[ \t]+(\n)")
_MANY_SPACES = re.compile(r"[ \t]{2,}")
_MANY_NEWLINES = re.compile(r"\n{3,}")
_PAGE_NUM_LINE = re.compile(r"^\s*(?:page\s+)?\d+(?:\s*/\s*\d+)?\s*$", re.IGNORECASE)


@dataclass(frozen=True)
class CleaningConfig:
    """Toggles for the cleaning pipeline. Defaults are safe for prose documents."""

    normalize_unicode: bool = True
    join_hyphenated_linebreaks: bool = True
    strip_control_chars: bool = True
    drop_page_number_lines: bool = True
    collapse_whitespace: bool = True
    # A line is treated as a running header/footer if it repeats on at least this
    # fraction of pages within a single source document.
    header_footer_min_page_fraction: float = 0.6
    header_footer_min_pages: int = 3


DEFAULT_CLEANING = CleaningConfig()


@dataclass
class CleanReport:
    """What cleaning changed for one text — surfaced by the F23 trace layer."""

    chars_before: int = 0
    chars_after: int = 0
    steps: list[str] = field(default_factory=list)

    @property
    def chars_removed(self) -> int:
        return self.chars_before - self.chars_after


def clean_text(
    text: str, config: CleaningConfig = DEFAULT_CLEANING
) -> tuple[str, CleanReport]:
    """Clean a single block of text. Returns (cleaned_text, report).

    Steps are applied in a fixed order and each is recorded in the report, so the
    transformation is fully explainable.
    """
    report = CleanReport(chars_before=len(text))
    out = text

    if config.normalize_unicode:
        out = unicodedata.normalize("NFKC", out)
        report.steps.append("normalize_unicode(NFKC)")
    if config.strip_control_chars:
        out = _CONTROL.sub("", out)
        report.steps.append("strip_control_chars")
    if config.join_hyphenated_linebreaks:
        out = _HYPHEN_BREAK.sub(r"\1\2", out)
        report.steps.append("join_hyphenated_linebreaks")
    if config.drop_page_number_lines:
        out = "\n".join(
            ln for ln in out.split("\n") if not _PAGE_NUM_LINE.match(ln)
        )
        report.steps.append("drop_page_number_lines")
    if config.collapse_whitespace:
        out = _TRAILING_WS.sub(r"\1", out)
        out = _MANY_SPACES.sub(" ", out)
        out = _MANY_NEWLINES.sub("\n\n", out)
        report.steps.append("collapse_whitespace")

    out = out.strip()
    report.chars_after = len(out)
    return out, report


def _detect_repeated_lines(pages: list[str], config: CleaningConfig) -> set[str]:
    """Find lines that recur across many pages of one document (headers/footers)."""
    if len(pages) < config.header_footer_min_pages:
        return set()
    counts: Counter[str] = Counter()
    for page in pages:
        # Consider only short-ish lines near the top/bottom-boundary noise; count once
        # per page even if a line appears multiple times on that page.
        seen_on_page = {
            ln.strip() for ln in page.split("\n") if 0 < len(ln.strip()) <= 120
        }
        counts.update(seen_on_page)
    threshold = max(
        config.header_footer_min_pages,
        int(len(pages) * config.header_footer_min_page_fraction),
    )
    return {line for line, n in counts.items() if n >= threshold}


def clean_documents(
    docs: list[Document], config: CleaningConfig = DEFAULT_CLEANING
) -> list[Document]:
    """Clean a list of page-Documents from one or more sources.

    Groups pages by ``source`` to detect and strip document-level running
    headers/footers, then applies :func:`clean_text` per page. Empty pages are dropped.
    Original metadata is preserved; a ``cleaned`` flag is stamped.
    """
    by_source: dict[str, list[Document]] = {}
    for d in docs:
        by_source.setdefault(d.metadata.get("source", ""), []).append(d)

    cleaned: list[Document] = []
    for _source, group in by_source.items():
        repeated = _detect_repeated_lines([d.page_content for d in group], config)
        for d in group:
            body = d.page_content
            if repeated:
                body = "\n".join(
                    ln for ln in body.split("\n") if ln.strip() not in repeated
                )
            text, _report = clean_text(body, config)
            if not text:
                continue
            meta = dict(d.metadata)
            meta["cleaned"] = True
            cleaned.append(Document(page_content=text, metadata=meta))
    return cleaned


def _shingles(text: str, size: int = 5) -> set[str]:
    words = re.findall(r"\w+", text.lower())
    if len(words) < size:
        return {" ".join(words)} if words else set()
    return {" ".join(words[i : i + size]) for i in range(len(words) - size + 1)}


def dedupe_chunks(chunks: list[Document], threshold: float = 0.9) -> list[Document]:
    """Drop near-duplicate chunks (Jaccard over word shingles >= threshold).

    Keeps the first occurrence. Guards against the common case where the same
    boilerplate paragraph is chunked repeatedly across a corpus.
    """
    kept: list[Document] = []
    kept_shingles: list[set[str]] = []
    for chunk in chunks:
        sig = _shingles(chunk.page_content)
        if not sig:
            kept.append(chunk)
            continue
        is_dup = False
        for prev in kept_shingles:
            inter = len(sig & prev)
            union = len(sig | prev)
            if union and inter / union >= threshold:
                is_dup = True
                break
        if not is_dup:
            kept.append(chunk)
            kept_shingles.append(sig)
    return kept
