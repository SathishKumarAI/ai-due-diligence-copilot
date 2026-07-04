#!/usr/bin/env bash
# Install the system OCR stack for feature F20 (Tesseract engine + Poppler for pdf2image).
#
# The Python bindings (pytesseract, pdf2image, pillow) come from requirements.txt;
# this script installs the *native* engines they call, which pip cannot provide.
#
# Linux only. On the Windows + GPU run host, install instead:
#   - Tesseract:  https://github.com/UB-Mannheim/tesseract/wiki  (add install dir to PATH)
#   - Poppler:    https://github.com/oschwartz10612/poppler-windows/releases
#                 (add the extracted bin/ to PATH, or pass poppler_path= to convert_from_path)
# See docs/INGESTION.md for the full Windows walkthrough.
set -euo pipefail

echo "Installing Tesseract + Poppler ..."

if command -v dnf >/dev/null 2>&1; then
  sudo dnf install -y tesseract poppler-utils
elif command -v apt-get >/dev/null 2>&1; then
  sudo apt-get update && sudo apt-get install -y tesseract-ocr poppler-utils
elif command -v brew >/dev/null 2>&1; then
  brew install tesseract poppler
else
  echo "No supported package manager (dnf/apt/brew) found. Install tesseract + poppler manually." >&2
  exit 1
fi

echo
echo "Verifying:"
tesseract --version | head -1 || { echo "tesseract not on PATH" >&2; exit 1; }
echo "OCR stack ready. Re-run 'python -m app.ingest' to OCR images / scanned PDFs in data/."
