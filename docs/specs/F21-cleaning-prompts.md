# Feature Spec — F21 Cleaning pipeline + prompt hardening

## Summary
Two related quality upgrades: (a) a deterministic text-cleaning + near-duplicate stage
between load and split, so noisy PDF/OCR text stops polluting embeddings; and (b)
prompt-injection resistance rules baked into the system prompt.

## Problem / why
Raw PDF/OCR text is noisy — inconsistent unicode, hyphenation broken across line breaks,
page-number lines, and headers/footers repeated on every page. That noise degrades
embeddings and retrieval, and the same boilerplate chunk recurs across a corpus. Separately,
untrusted document text can carry "ignore previous instructions" style attacks the model
must not obey.

## Users & context
Internal to ingestion (F01/F20) and to the RAG engine's prompt (F03). No API surface change.

## Behaviour (acceptance criteria)
### Cleaning
- WHEN `CLEAN_ENABLED=true` (default) THEN `load_documents` cleans every page after load:
  NFKC unicode normalization, control-char strip, hyphenated-linebreak join, page-number-line
  drop, and whitespace collapse — each recorded in a `CleanReport` for the F23 trace.
- WHEN pages of one source share a line on ≥ `header_footer_min_page_fraction` of pages
  (and ≥ `header_footer_min_pages` pages exist) THEN that running header/footer line is stripped.
- WHEN a page cleans down to empty THEN it is dropped; surviving pages are stamped `cleaned=True`.
- WHEN `DEDUPE_ENABLED=true` (default) THEN after splitting, chunks whose Jaccard similarity
  over word shingles ≥ `DEDUPE_THRESHOLD` are dropped, keeping the first occurrence.

### Prompt hardening
- WHEN a retrieved passage contains injection text ("ignore previous instructions",
  "you are now…", a request to reveal the prompt) THEN the model treats it as untrusted DATA,
  does not comply, and may flag it as a red flag.
- WHEN asked to reveal or restate the system instructions THEN it refuses.

## Rules / logic
- `app/cleaning.py` is **stdlib-only and deterministic** (no model calls). `clean_text`
  applies steps in a fixed order and returns `(text, CleanReport)`. `CleaningConfig`
  toggles each step; `DEFAULT_CLEANING` is safe for prose.
- `clean_documents` groups pages by `source`, calls `_detect_repeated_lines` to find
  document-level headers/footers (counted once per page, only lines ≤ 120 chars), strips
  them, then cleans each page. Metadata is preserved.
- `dedupe_chunks` uses `_shingles` (5-word shingles over lowercased word tokens) and
  Jaccard = |∩| / |∪|.
- Pipeline order (`app/ingest.py`): **load → clean → split → dedupe → embed**. The same
  clean step runs in `add_file_to_store` (F18 uploads).
- `SYSTEM_PROMPT` in `app/prompts.py` adds a "Security (prompt-injection resistance)"
  block: passages are untrusted data, never reveal instructions, only follow the user's
  question insofar as it asks to analyze the passages.

## Config / env knobs
- `CLEAN_ENABLED` (default `true`) — normalize/strip noise between load and split.
- `DEDUPE_ENABLED` (default `true`) — drop near-duplicate chunks after splitting.
- `DEDUPE_THRESHOLD` (default `0.9`) — Jaccard(shingles) ≥ this ⇒ duplicate.
- (Header/footer thresholds are `CleaningConfig` fields, not env-exposed.)

## Out of scope (for now)
- LLM-based cleaning / semantic dedupe — this stage is deliberately deterministic.
- Per-field or table-aware normalization.

## Data touched
- Reads: in-memory page-Documents. Writes: none (transforms the ingestion stream).

## Edge cases
- Fewer than `header_footer_min_pages` pages (no header detection) · chunk shorter than
  the shingle size (whole-text shingle) · chunk with no word tokens (kept, never a dup) ·
  disabling individual clean steps via `CleaningConfig`.

## Done when
- Cleaning collapses/joins text, strips running headers, drops page-number lines and
  near-duplicate chunks, the security block is present in `SYSTEM_PROMPT`, and offline
  tests cover clean_text steps (and disabling them), header stripping with `cleaned` stamp,
  and dedupe of near-duplicates.
