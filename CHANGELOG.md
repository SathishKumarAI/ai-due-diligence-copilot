# Changelog

All notable changes to this project are documented here. Format follows
[Keep a Changelog](https://keepachangelog.com/en/1.1.0/); versions follow
[Semantic Versioning](https://semver.org/).

The same notes, in plain language, are published as
[GitHub Releases](../../releases) and surfaced in the app's **What's New** page.

## [Unreleased]
### Added
- `scripts/generate_synthetic_data.py` — reproducible generator for the synthetic
  deal-document corpus (seedable; no LLM/network).

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
