"""OCR text extraction for scanned PDFs and image files (feature F20).

Fully local, no cloud and no API keys: text is extracted with **Tesseract** via
``pytesseract``, and scanned-PDF pages are rasterized with ``pdf2image`` before OCR.

Where this fits in ingestion (F01):

    image (.png/.jpg/...) ─┐
    scanned PDF (no text) ─┼─► this module (Tesseract) ─► Document(text, extraction_method="ocr")
    text-layer PDF ────────┘   (handled by the normal PyPDFLoader, extraction_method="text")

Design notes
------------
- **Lazy imports.** ``pytesseract``, ``pdf2image`` and ``PIL`` are imported inside the
  functions that need them, so this module (and the offline test-suite) imports cleanly
  on machines without the OCR stack installed. Call :func:`ocr_available` to probe.
- **Only OCR when needed.** :func:`pdf_needs_ocr` checks the PDF's text layer first, so
  born-digital PDFs never pay the OCR cost.
- **Metadata.** Every returned Document carries ``source``, ``page`` and
  ``extraction_method`` ("ocr") so the pipeline-trace layer (F23) can show *how* each
  chunk's text was obtained.

System engine install: ``scripts/install-ocr.sh`` (Linux) or the Windows notes in
``docs/INGESTION.md`` (this project is authored on Linux but run on a Windows+GPU host).
"""

from __future__ import annotations

import logging
import shutil
from pathlib import Path

from langchain_core.documents import Document

logger = logging.getLogger(__name__)

# Raster image formats Tesseract can read directly.
IMAGE_SUFFIXES: frozenset[str] = frozenset(
    {".png", ".jpg", ".jpeg", ".tif", ".tiff", ".bmp", ".webp"}
)


def ocr_available() -> bool:
    """True if the OCR stack (python bindings + the tesseract binary) is usable.

    Kept import-safe: returns False instead of raising when deps are missing, so
    callers can degrade gracefully (e.g. skip image files with a warning).
    """
    if shutil.which("tesseract") is None:
        return False
    try:  # python bindings present?
        import pdf2image  # noqa: F401
        import pytesseract  # noqa: F401
    except ImportError:
        return False
    return True


def _require_ocr() -> None:
    if not ocr_available():
        raise RuntimeError(
            "OCR requested but the Tesseract stack is unavailable. Install the engine "
            "(scripts/install-ocr.sh on Linux; UB-Mannheim installer on Windows) and "
            "`pip install pytesseract pdf2image pillow`."
        )


def pdf_needs_ocr(path: Path, min_chars_per_page: int = 40) -> bool:
    """Decide whether a PDF is scanned (image-only) and therefore needs OCR.

    Reads the existing text layer with pypdf and compares the average characters per
    page against ``min_chars_per_page``. Born-digital PDFs return False (skip OCR);
    scanned/photographed PDFs return True. On any read error we assume OCR is needed.
    """
    try:
        from pypdf import PdfReader

        reader = PdfReader(str(path))
        pages = reader.pages
        if not pages:
            return True
        total = sum(len((p.extract_text() or "").strip()) for p in pages)
        return (total / len(pages)) < min_chars_per_page
    except Exception:  # noqa: BLE001 - unreadable text layer => treat as scanned
        logger.warning("pdf_text_probe_failed source=%s -> assuming scanned", path.name)
        return True


def ocr_image(path: Path, lang: str = "eng") -> list[Document]:
    """OCR a single image file into a one-page Document."""
    _require_ocr()
    import pytesseract
    from PIL import Image

    with Image.open(path) as img:
        text = pytesseract.image_to_string(img, lang=lang)
    return [
        Document(
            page_content=text,
            metadata={"source": path.name, "page": 1, "extraction_method": "ocr"},
        )
    ]


def ocr_pdf(path: Path, lang: str = "eng", dpi: int = 200) -> list[Document]:
    """OCR every page of a scanned PDF, one Document per page (1-indexed)."""
    _require_ocr()
    import pytesseract
    from pdf2image import convert_from_path

    images = convert_from_path(str(path), dpi=dpi)
    docs: list[Document] = []
    for i, image in enumerate(images, start=1):
        text = pytesseract.image_to_string(image, lang=lang)
        docs.append(
            Document(
                page_content=text,
                metadata={"source": path.name, "page": i, "extraction_method": "ocr"},
            )
        )
    logger.info("ocr_pdf_complete source=%s pages=%d", path.name, len(docs))
    return docs


def load_with_ocr(path: Path, lang: str = "eng", dpi: int = 200) -> list[Document]:
    """Dispatch an image or scanned PDF to the right OCR path.

    Callers should only route files here that actually need OCR (images always;
    PDFs only when :func:`pdf_needs_ocr` is True).
    """
    suffix = path.suffix.lower()
    if suffix in IMAGE_SUFFIXES:
        return ocr_image(path, lang=lang)
    if suffix == ".pdf":
        return ocr_pdf(path, lang=lang, dpi=dpi)
    raise ValueError(f"OCR not supported for {suffix}")
