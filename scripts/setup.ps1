# Native (no-Docker) setup for Windows (PowerShell). Creates a venv, installs deps, and —
# with -Gpu — installs CUDA torch wheels and checks the NVIDIA driver.
#
#   .\scripts\setup.ps1          # CPU
#   .\scripts\setup.ps1 -Gpu     # NVIDIA CUDA torch (RTX)
param([switch]$Gpu)
$ErrorActionPreference = "Stop"
Set-Location (Join-Path $PSScriptRoot "..")

# A venv built on Linux (this repo is authored there) has bin/ instead of Scripts/, and
# `python -m venv` will not repair it. Fail loudly instead of dying on the activate line.
if ((Test-Path .venv) -and -not (Test-Path .\.venv\Scripts\Activate.ps1)) {
  throw "A .venv exists but has no Scripts\Activate.ps1 - it was built on another platform. Delete it and re-run."
}

Write-Host "==> Creating venv (.venv)"
python -m venv .venv
. .\.venv\Scripts\Activate.ps1
python -m pip install --upgrade pip

if ($Gpu) {
  # cu128, not cu124: Blackwell (RTX 50-series) is sm_120, and cu124 wheels ship no sm_120
  # kernels - torch imports fine, then fails at the first CUDA op. cu128 covers sm_75..sm_120.
  Write-Host "==> Installing CUDA torch (cu128)"
  pip install torch --index-url https://download.pytorch.org/whl/cu128
  if (Get-Command nvidia-smi -ErrorAction SilentlyContinue) { nvidia-smi -L }
  else { Write-Warning "nvidia-smi not found - install the NVIDIA driver, or run CPU mode." }
}

Write-Host "==> Installing app deps"
pip install -r requirements.txt

Write-Host @"

Native run - next steps:
  1. Ollama:    https://ollama.com/download/windows   then:  ollama pull llama3.1:8b
  2. OCR (F20): Tesseract  https://github.com/UB-Mannheim/tesseract/wiki   (add install dir to PATH)
                Poppler    https://github.com/oschwartz10612/poppler-windows/releases  (add bin\ to PATH)
  3. copy .env.example .env    # set EMBED_DEVICE / RERANK_DEVICE (auto|cpu|cuda)
  4. python -m app.ingest      # build the index
  5. uvicorn app.main:app      # http://localhost:8000
"@
