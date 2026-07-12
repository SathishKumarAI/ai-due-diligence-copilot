# Changelog

All notable changes to this project are documented here. Format follows
[Keep a Changelog](https://keepachangelog.com/en/1.1.0/); versions follow
[Semantic Versioning](https://semver.org/).

The same notes, in plain language, are published as
[GitHub Releases](../../releases) and surfaced in the app's **What's New** page.

## [Unreleased]
### Added
- **Fully-local guard (`LOCAL_ONLY`).** Runs local-only by default: `LOCAL_ONLY=true`
  refuses the Claude/Voyage cloud provider even if `PROVIDER=claude`. Set `LOCAL_ONLY=false`
  to opt into the cloud path. Enforced at the provider seam (`app/providers.py`).
- **GPU + no-Docker deployment.** New-device setup now has two paths (Docker / native)
  each in CPU or GPU mode, on Windows/RTX, Linux, and macOS. Added `Dockerfile.gpu`
  (CUDA 12.4 + torch cu124 + OCR stack), `docker-compose.gpu.yml` (reserves the GPU for
  API + Ollama), `scripts/setup.sh` / `scripts/setup.ps1` native bootstrappers,
  `.dockerignore`, and `docs/DEPLOYMENT.md`. Embeddings and the F17 reranker now honor
  `EMBED_DEVICE` / `RERANK_DEVICE` (`auto` = cuda→mps→cpu) via new `app/device.py`.
- `scripts/generate_synthetic_data.py` — reproducible generator for the synthetic
  deal-document corpus (seedable; no LLM/network).
- **F16 — Hybrid retrieval.** Lexical BM25 (dependency-free, in-process) fused with
  dense vector search via Reciprocal Rank Fusion; lifts recall on exact figures and
  codes. Toggle with `RETRIEVAL_MODE=hybrid|dense`.
- **F17 — Cross-encoder re-ranker.** Optional `RERANK_ENABLED` pass that re-scores
  retrieved candidates with a cross-encoder (via the already-bundled
  `sentence-transformers`) before generation.
- **F18 — Per-document upload.** `POST /v1/upload` (raw body, no new dependency) and
  a web upload control add a PDF/Markdown/text file to the live index; re-upload of
  the same name replaces it.
- **F19 — Conversation memory + feedback.** `/v1/ask` accepts prior `history` and
  condenses follow-ups into standalone queries; new `POST /v1/feedback` captures
  👍/👎 to `data/feedback.jsonl` for a usage-grounded eval set.
- **Web UI redesign.** Chat-style multi-turn interface with token streaming, inline
  clickable citation chips, document upload, answer feedback, a live index-health
  badge, and light/dark themes.

### Changed
- `RagEngine` now depends on small `Retriever` / `Reranker` seams (injectable,
  faked in tests) rather than calling the vector store directly.

## [0.1.0] — 2026-06-23
### Added
- RAG pipeline: ingest (load → chunk → embed → Chroma), retrieval, and grounded
  answers with `[n]` citations mapped to real source passages.
- Pluggable model providers via a `PROVIDER` switch: open-source Ollama + HuggingFace
  embeddings (default, free) or Claude + Voyage.
- FastAPI service: `/v1/ask`, `/v1/ask/stream` (SSE), `/v1/ingest`, `/v1/sources`,
  `/health`, `/ready`, `/metrics`.
- Production concerns: API-key auth + rate limiting, structured JSON logging with
  request IDs, Prometheus metrics, answer + embedding caching.
- Evaluation harness (retrieval hit-rate + LLM-as-judge faithfulness) wired as a CI gate.
- Next.js web UI for non-technical users (Ask page + What's New page).
- Containerization (multi-stage non-root Dockerfile + compose) and CI (ruff, mypy,
  pytest, docker build).
- Full doc kit under `docs/` (architecture, specs F01–F15, security, runbook, ADRs).

[Unreleased]: https://github.com/SathishKumarAI/ai-due-diligence-copilot/compare/v0.1.0...HEAD
[0.1.0]: https://github.com/SathishKumarAI/ai-due-diligence-copilot/releases/tag/v0.1.0
