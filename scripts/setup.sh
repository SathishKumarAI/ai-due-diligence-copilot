#!/usr/bin/env bash
# Native (no-Docker) setup for Linux/macOS. Creates a venv, installs deps, and — with
# --gpu — installs CUDA torch wheels. Prints Ollama + OCR (Tesseract/Poppler) next steps.
#
#   ./scripts/setup.sh            # CPU
#   ./scripts/setup.sh --gpu      # NVIDIA CUDA torch (Linux); macOS uses MPS on the default wheel
set -euo pipefail

GPU=0
[[ "${1:-}" == "--gpu" ]] && GPU=1
cd "$(dirname "$0")/.."

PY=${PYTHON:-python3}
echo "==> Creating venv (.venv) with $("$PY" --version)"
"$PY" -m venv .venv
# shellcheck disable=SC1091
source .venv/bin/activate
python -m pip install --upgrade pip

if [[ $GPU -eq 1 ]]; then
  if [[ "$(uname -s)" == "Darwin" ]]; then
    echo "==> macOS: no CUDA. torch MPS ships in the default wheel — set EMBED_DEVICE=auto (uses mps)."
  else
    echo "==> Installing CUDA torch (cu124)"
    pip install torch --index-url https://download.pytorch.org/whl/cu124
    if command -v nvidia-smi >/dev/null 2>&1; then nvidia-smi -L; else
      echo "WARN: nvidia-smi not found — install the NVIDIA driver, or run CPU mode."
    fi
  fi
fi

echo "==> Installing app deps"
pip install -r requirements.txt

cat <<'EOF'

Native run — next steps:
  1. Ollama:    https://ollama.com/download    then:  ollama pull llama3.1:8b
  2. OCR (F20): ./scripts/install-ocr.sh        (Tesseract + Poppler)
  3. cp .env.example .env                        # set EMBED_DEVICE / RERANK_DEVICE (auto|cpu|cuda|mps)
  4. python -m app.ingest                        # build the index
  5. make run                                    # http://localhost:8000
EOF
