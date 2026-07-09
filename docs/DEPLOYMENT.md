# Deployment — running on a new device

Two independent install paths, each in **CPU** or **GPU** mode, on **Windows/RTX, Linux, or macOS**.
Pick a row.

| Path | CPU | GPU (NVIDIA) | Best for |
|------|-----|--------------|----------|
| **Docker** | `docker compose up --build` | `docker compose -f docker-compose.yml -f docker-compose.gpu.yml up --build` | reproducible, isolated |
| **Native** (no Docker) | `./scripts/setup.sh` / `.\scripts\setup.ps1` | `./scripts/setup.sh --gpu` / `.\scripts\setup.ps1 -Gpu` | dev, direct GPU, laptops |

**What "GPU" accelerates:** the LLM (Ollama), the embedding model, and the F17 cross-encoder
reranker. Ollama manages its own GPU; embeddings/reranker use torch on the device set by
`EMBED_DEVICE` / `RERANK_DEVICE` (`auto` = cuda → mps → cpu, or force `cuda|cpu|mps`).

---

## Prerequisites

| | Docker path | Native path |
|---|---|---|
| Runtime | Docker + Docker Compose v2 | Python 3.11+ (3.12 recommended) |
| GPU (NVIDIA) | NVIDIA driver + [NVIDIA Container Toolkit](https://docs.nvidia.com/datacenter/cloud-native/container-toolkit/latest/install-guide.html) | NVIDIA driver (`nvidia-smi` works) |
| LLM | bundled Ollama container | [Ollama](https://ollama.com/download) installed on host |
| OCR (F20, optional) | baked into the GPU image; add to CPU image if needed | Tesseract + Poppler on PATH |

---

## Docker

CPU is the default and needs nothing but Docker:

```bash
docker compose up --build
docker compose exec ollama ollama pull llama3.1:8b   # one-time model pull
```

GPU adds the overlay (requires the NVIDIA Container Toolkit):

```bash
docker compose -f docker-compose.yml -f docker-compose.gpu.yml up --build
docker compose exec ollama ollama pull llama3.1:8b
```

The overlay builds `Dockerfile.gpu` (CUDA 12.4 base + CUDA torch + Tesseract/Poppler),
reserves the GPU for **both** the API and Ollama, and sets `EMBED_DEVICE=RERANK_DEVICE=cuda`.
Verify the API sees the GPU:

```bash
docker compose exec api python3.12 -c "import torch; print(torch.cuda.is_available())"   # True
```

API on `http://localhost:8000` (`/docs`, `/health`, `/metrics`). Index data with:
`docker compose exec api python3.12 -m app.ingest`.

---

## Native (no Docker)

One script bootstraps a venv and installs deps. Add the GPU flag for CUDA torch.

### Windows + RTX (PowerShell)

```powershell
.\scripts\setup.ps1 -Gpu          # venv + deps + CUDA torch; omit -Gpu for CPU
# install Ollama (https://ollama.com/download/windows), then:
ollama pull llama3.1:8b
# OCR (optional): Tesseract (UB-Mannheim) + Poppler for Windows, both added to PATH
copy .env.example .env            # EMBED_DEVICE / RERANK_DEVICE = auto (uses the GPU)
.\.venv\Scripts\Activate.ps1
python -m app.ingest
uvicorn app.main:app              # http://localhost:8000
```

### Linux + NVIDIA (bash)

```bash
./scripts/setup.sh --gpu          # venv + deps + CUDA torch; omit --gpu for CPU
# install Ollama (https://ollama.com/download) — it uses the GPU automatically
ollama pull llama3.1:8b
bash scripts/install-ocr.sh       # Tesseract + Poppler (optional, OCR)
cp .env.example .env
source .venv/bin/activate
python -m app.ingest
make run                          # http://localhost:8000
```

### macOS (Apple Silicon)

No NVIDIA/CUDA. torch uses **MPS** (Metal) automatically under `EMBED_DEVICE=auto`;
Ollama uses its own Metal backend. There is no Docker-GPU path on macOS — use native.

```bash
./scripts/setup.sh                # default wheel already includes MPS
brew install ollama tesseract poppler && ollama serve &
ollama pull llama3.1:8b
cp .env.example .env              # auto -> mps for embeddings/reranker
source .venv/bin/activate && python -m app.ingest && make run
```

---

## Cloud provider (no local GPU)

Skip Ollama/torch entirely — use Claude + Voyage. Set in `.env`:

```
PROVIDER=claude
ANTHROPIC_API_KEY=...
VOYAGE_API_KEY=...
```

Embeddings run on Voyage's API, so `EMBED_DEVICE` / `RERANK_DEVICE` are irrelevant
(the reranker only loads when `RERANK_ENABLED=true`).

---

## Production notes

- **Secrets:** `.env` only (gitignored). Set `API_KEY` to require `X-API-Key`; tune
  `RATE_LIMIT_PER_MIN`. Restrict `CORS_ORIGINS` from `*` to your frontend origin.
- **Health/monitoring:** `/health` (liveness), `/ready` (readiness), `/metrics`
  (Prometheus). Compose images ship a `HEALTHCHECK`; the GPU overlay adds `restart: unless-stopped`.
- **Persistence:** the Chroma index lives in `chroma_db/` (a named volume in compose).
  Re-run ingest after adding documents.
- **Non-root:** both images run as UID 10001.
- **First run is slow:** embedding/reranker models download once, then cache.

## Troubleshooting

| Symptom | Fix |
|---|---|
| `torch.cuda.is_available()` is `False` in Docker | Install the NVIDIA Container Toolkit; confirm `docker run --rm --gpus all nvidia/cuda:12.4.1-base-ubuntu22.04 nvidia-smi`. |
| Native GPU not used | `nvidia-smi` must work; reinstall torch with `--index-url https://download.pytorch.org/whl/cu124`. |
| Out of GPU memory | Use a smaller Ollama model (e.g. `llama3.1:8b` → quantized), or set `RERANK_ENABLED=false`. |
| OCR does nothing | Tesseract/Poppler not on PATH (native) — see `scripts/install-ocr.sh` or the Windows links above. |
