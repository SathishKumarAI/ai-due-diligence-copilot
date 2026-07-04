# Feature Spec — F20 OCR ingestion (images + scanned PDFs)

## Summary
Extract text from image files and scanned (image-only) PDFs during ingestion using a
fully local Tesseract stack, so photographed decks and scanned filings become
searchable alongside born-digital documents.

## Problem / why
Due-diligence material arrives as scans and screenshots — a photographed term sheet, a
faxed 10-K, a slide exported as PNG. `PyPDFLoader` reads none of that (no text layer),
so those documents are invisible to retrieval. Local OCR recovers the text without any
cloud call or API key.

## Users & context
Internal to the ingestion pipeline (F01). Feeds `load_one` in `app/ingest.py`; also
covers `/v1/upload` (F18), which accepts image files. No new API surface.

## Behaviour (acceptance criteria)
- WHEN an image file (`.png/.jpg/.jpeg/.tif/.tiff/.bmp/.webp`) is ingested AND OCR is
  enabled and available THEN it is OCR'd into a one-page Document (`extraction_method="ocr"`).
- WHEN a PDF's average text-layer length is below `ocr_min_chars_per_page` THEN
  `pdf_needs_ocr` returns True and every page is rasterized and OCR'd.
- WHEN a PDF has a real text layer THEN it uses `PyPDFLoader` unchanged (`extraction_method="text"`),
  never paying the OCR cost.
- WHEN `OCR_ENABLED=false` OR the Tesseract stack is absent THEN image files are skipped
  with a warning and PDFs fall back to the text-layer loader (graceful degradation).
- WHEN a PDF text layer is unreadable THEN `pdf_needs_ocr` assumes scanned (returns True).

## Rules / logic
- `app/ocr.py` — `ocr_available()` probes both the `tesseract` binary (`shutil.which`)
  and the Python bindings; `pytesseract`, `pdf2image`, and `PIL` are **lazily imported**
  inside functions so the module (and the offline test-suite) imports cleanly without the
  OCR stack. `_require_ocr()` raises a clear install hint when OCR is requested but missing.
- `pdf_needs_ocr(path, min_chars_per_page)` reads the pypdf text layer and compares
  average chars/page to the threshold.
- `ocr_image` (one page), `ocr_pdf` (rasterize via `convert_from_path` at `dpi`, one
  Document per 1-indexed page), and `load_with_ocr` dispatch by suffix.
- Every OCR Document carries `source`, `page`, and `extraction_method="ocr"` — the last
  is what the F23 trace layer surfaces per chunk.
- `scripts/install-ocr.sh` installs the **native** engines (Tesseract + Poppler) via
  dnf/apt/brew; the Python bindings come from `requirements.txt`.

## Config / env knobs
- `OCR_ENABLED` (default `true`) — OCR images + scanned PDFs during ingest.
- `OCR_LANG` (default `eng`) — Tesseract language pack(s), e.g. `eng+deu`.
- `OCR_DPI` (default `200`) — rasterization DPI for scanned PDF pages.
- `OCR_MIN_CHARS_PER_PAGE` (default `40`) — below this average a PDF is treated as scanned.

## Out of scope (for now)
- Cloud OCR / hosted document AI (the seam is local-only by design).
- Layout/table reconstruction — plain text extraction only.

## Data touched
- Reads: image + PDF files under `data_dir`. Writes: none (produces in-memory Documents).
  Tesseract/Poppler are external native binaries.

## Edge cases
- Image with no readable text (empty page) · scanned PDF with a partial text layer ·
  unsupported suffix routed to `load_with_ocr` (raises `ValueError`) · OCR stack present
  but `OCR_ENABLED=false` (images skipped).

## Done when
- Images and scanned PDFs ingest with `extraction_method="ocr"`, born-digital PDFs stay
  on the text path, and offline tests cover the import-safe paths: `ocr_available` returns
  a bool, `pdf_needs_ocr` assumes scanned on a bad path, `load_with_ocr` rejects an
  unsupported suffix, and `IMAGE_SUFFIXES` covers common formats — none downloading a model.
