# Design — GPU run files + Docker-optional deployment

**Date:** 2026-07-09 · **Status:** approved · **Scope:** all 3 sibling RAG repos (FIN reference → MED/ENG)

## Problem

The apps ship F01–F23 and are public, but the run story is incomplete:

- **No GPU path.** `Dockerfile` is `python:3.12-slim` (CPU). Embeddings (`HuggingFaceEmbeddings`)
  and the F17 cross-encoder reranker (`CrossEncoder`) take no `device` argument, so they pin to CPU.
  `docker-compose.yml` gives Ollama no GPU. On the Windows/RTX host nothing uses the GPU.
- **No no-Docker path for a fresh device.** Only `make setup` exists; no bootstrap that stands up
  a venv + native deps + GPU torch across OSes.
- **New-device setup is undocumented** beyond scattered README notes.

## Goals

1. Optional GPU acceleration for LLM (Ollama), embeddings, and reranker.
2. Two independent install paths — **Docker** and **native (no Docker)** — each in **CPU or GPU** mode.
3. One deployment guide covering **Windows/RTX, Linux, macOS**.
4. Keep the CPU Docker path as the zero-config default. Zero new Python deps. No engine drift.

## Non-goals

- Kubernetes / cloud deploy manifests. Multi-GPU sharding. Running/benchmarking here
  (no local execution on the build machine — verified on the Windows/RTX host).

## Design

### Engine changes (shared, replicated by `sync_engine.py`)

- **`app/device.py` (new)** — `resolve_device(preference="auto") -> str`.
  Explicit `cpu|cuda|mps` pass through. `auto` lazily imports torch and returns
  `cuda` → `mps` → `cpu`. Guarded import; never raises. Added to `SHARED_ENGINE_FILES`.
- **`app/providers.py`** — embeddings get `model_kwargs={"device": resolve_device(settings.embed_device)}`.
- **`app/rerank.py`** — `CrossEncoderReranker(model_name, device)`; `build_reranker` passes
  `settings.rerank_device`; `CrossEncoder(..., device=...)`.
- **`tests/test_device.py` (new)** — pure assertions on `resolve_device`; no GPU, no model download.

### Per-project change

- **`app/config.py`** — add `embed_device: str = "auto"`, `rerank_device: str = "auto"`
  (config.py is per-repo, so edited by hand in each).

### Docker — GPU optional

- **`Dockerfile.gpu` (new)** — `nvidia/cuda:12.4.1-runtime-ubuntu22.04` + Python 3.12 +
  torch cu124 wheels + tesseract/poppler in-image (OCR works in-container). Non-root, same healthcheck.
- **`docker-compose.gpu.yml` (new)** — overrides adding NVIDIA
  `deploy.resources.reservations.devices` to **api and ollama**, builds `Dockerfile.gpu`,
  sets `EMBED_DEVICE=cuda` / `RERANK_DEVICE=cuda`, `restart: unless-stopped`.
  Used as `docker compose -f docker-compose.yml -f docker-compose.gpu.yml up`.
- **`.dockerignore` (new)** — drop `.venv`, caches, `chroma_db`, `web/node_modules`, `.git`.

### Native (no-Docker) path

- **`scripts/setup.sh`** (Linux/macOS) and **`scripts/setup.ps1`** (Windows/RTX) — create venv,
  pip install, `--gpu` installs torch CUDA wheels + checks `nvidia-smi`, print Ollama +
  Tesseract/Poppler guidance. Wrap existing Makefile targets.

### Docs + config

- **`docs/DEPLOYMENT.md` (new)** — matrix `{Docker, Native} × {CPU, GPU} × {Windows/RTX, Linux, macOS}`,
  Windows/RTX walkthrough first.
- **`.env.example`** — `EMBED_DEVICE`, `RERANK_DEVICE`. **`README.md`** — short run matrix → DEPLOYMENT.md.
- **`.github/workflows/ci.yml`** — build-only `docker build -f Dockerfile.gpu` (no GPU needed to build).

## Replication

Build + review in FIN. `python scripts/sync_engine.py --to ../MED ../ENG` carries the engine
(after `device.py` is added to the list). Infra files (Dockerfile.gpu, compose, .dockerignore,
scripts, DEPLOYMENT.md, CI) are domain-neutral and copied identically. `config.py`, `.env.example`,
`README.md` hand-edited per repo. `ENGINE_MANIFEST.sha256` regenerated; `tests/test_parity.py` guards drift.

## macOS caveat

No NVIDIA. GPU there = torch MPS for embeddings/reranker; Ollama uses its own Metal backend
natively (not Docker GPU). Documented as such.
