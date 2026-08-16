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
# A venv built on Windows has Scripts/ instead of bin/, and `python -m venv` will not repair
# it. Fail loudly instead of dying on the source line.
if [[ -d .venv && ! -f .venv/bin/activate ]]; then
  echo "ERROR: a .venv exists but has no bin/activate — it was built on another platform. Delete it and re-run." >&2
  exit 1
fi

echo "==> Creating venv (.venv) with $("$PY" --version)"
"$PY" -m venv .venv
# shellcheck disable=SC1091
source .venv/bin/activate
python -m pip install --upgrade pip

if [[ $GPU -eq 1 ]]; then
  if [[ "$(uname -s)" == "Darwin" ]]; then
    echo "==> macOS: no CUDA. torch MPS ships in the default wheel — set EMBED_DEVICE=auto (uses mps)."
  else
    # cu128, not cu124: Blackwell (RTX 50-series) is sm_120, and cu124 wheels ship no sm_120
    # kernels — torch imports fine, then fails at the first CUDA op. cu128 covers sm_75..sm_120.
    #
    # Pin to the lockfile's version: an unpinned CUDA install followed by the lock lets
    # pip replace the working GPU build with the CPU wheel from PyPI, and the only
    # symptom is torch.cuda.is_available() silently turning False.
    TORCH_PIN=$(grep '^torch==' requirements.lock || true)
    [[ -n "$TORCH_PIN" ]] || { echo "No torch pin in requirements.lock" >&2; exit 1; }
    echo "==> Installing CUDA torch (cu128): $TORCH_PIN"
    pip install "$TORCH_PIN" --index-url https://download.pytorch.org/whl/cu128
    if command -v nvidia-smi >/dev/null 2>&1; then nvidia-smi -L; else
      echo "WARN: nvidia-smi not found — install the NVIDIA driver, or run CPU mode."
    fi
  fi
fi

# The lockfile, not requirements.txt: the ranges there resolved to a different ruff,
# numpy and langchain in July than they do today, which is what broke the quality gate
# and hid two failing tests. Regenerate with scripts/lock.sh when a range changes.
echo "==> Installing app deps (locked)"
pip install -r requirements.lock

cat <<'EOF'

Native run — next steps:
  1. Ollama:    https://ollama.com/download    then:  ollama pull llama3.1:8b
  2. OCR (F20): ./scripts/install-ocr.sh        (Tesseract + Poppler)
  3. cp .env.example .env                        # set EMBED_DEVICE / RERANK_DEVICE (auto|cpu|cuda|mps)
  4. python -m app.ingest                        # build the index
  5. make run                                    # http://localhost:8000
EOF
