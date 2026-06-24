# Feature Spec — F01 Document ingestion pipeline

## Summary
Load the documents in `data/`, split them into chunks, embed them, and persist them
to a Chroma collection so they can be retrieved.

## Problem / why
Retrieval works on small, embedded chunks — not whole files. Without a reliable,
repeatable ingest step there's nothing to search.

## Users & context
A developer (or the `/v1/ingest` endpoint) runs ingest after adding/changing docs.

## Behaviour (acceptance criteria)
- WHEN `python -m app.ingest` runs THEN every `.pdf/.md/.txt` under `data/` is loaded,
  chunked, embedded, and stored in the configured Chroma collection.
- WHEN a chunk is stored THEN it carries `source` (filename) and `page` metadata.
- WHEN ingest is re-run THEN the collection is rebuilt to match the current corpus
  (idempotent — no duplicate chunks).
- WHEN `data/` has no supported files THEN it raises a clear error, not a silent empty index.

## Rules / logic
- Loaders: `PyPDFLoader` for `.pdf`, `TextLoader` for `.md/.txt/.markdown`.
- Splitter: `RecursiveCharacterTextSplitter(chunk_size, chunk_overlap, add_start_index)`.
- Embeddings come from the provider seam, wrapped in the embedding cache (F07).
- Idempotency: `reset_collection()` before `add_documents`.

## Out of scope (for now)
- Per-document upload via the UI (P2). Incremental/delta ingest (currently full rebuild).

## Data touched
- Reads: files under `settings.data_dir`.
- Writes: `chroma_db/` (the persisted collection).

## Edge cases
- Empty corpus → error. Unsupported file types → skipped. PDF with no text → empty
  chunks for that file (no crash).

## Done when
- `tests/test_chunking.py` passes (split preserves `source`; corpus loads).
- `python -m app.ingest` prints documents + chunk counts; re-running yields the same count.
