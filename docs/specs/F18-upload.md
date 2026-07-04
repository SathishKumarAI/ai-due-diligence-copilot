# Feature Spec — F18 Per-document upload via UI

## Summary
Let a non-technical user add their own document (PDF / Markdown / text) through the
web UI; the file is persisted, chunked, embedded, and merged into the live index
without a full re-ingest.

## Problem / why
Today the corpus is fixed at ingest time. Users want to drop in the deck or 10-K
they're actually evaluating and ask about it immediately.

## Users & context
Web UI users via an Upload control; programmatic callers via `POST /v1/upload`.

## Behaviour (acceptance criteria)
- WHEN a supported file is uploaded THEN it is saved under `data/uploads/`, split,
  embedded, and added to the Chroma collection, and the response reports chunks added.
- WHEN the index already contained chunks for the same filename THEN those prior
  chunks are removed first (idempotent re-upload).
- WHEN the file type is unsupported THEN the API returns 415 with a clear message.
- WHEN the file is empty / unreadable THEN the API returns 400 and the index is
  unchanged.
- WHEN auth is configured THEN `/v1/upload` requires the API key (like all `/v1/*`).

## Rules / logic
- Endpoint reads the raw request body (no `python-multipart` dependency); the
  filename comes from a `filename` query param, sanitized to a basename.
- Supported suffixes match F01: `.pdf .md .markdown .txt`.
- After add, the in-memory BM25 index (F16) is rebuilt so lexical retrieval sees the
  new chunks.

## Out of scope (for now)
- Multi-file / bulk upload · virus scanning · per-user corpora / tenancy.

## Data touched
- Writes: `data/uploads/<name>` and new chunks in the Chroma collection. Reads: same.

## Edge cases
- Duplicate filename (replace) · path-traversal in filename (stripped to basename) ·
  very large file (bounded by `max_upload_mb`) · upload before any initial ingest.

## Done when
- Uploading a known fixture makes its content answerable with a citation to it, and
  unit tests cover add, idempotent replace, and the unsupported/empty rejections.
