---
title: Backlog
description: Prioritized features and what's next. Tier: Core.
sidebar_position: 2
---

# Backlog

> Prioritized work. Each shipped feature links to its spec (the source of truth).
> P0 = core RAG correctness, P1 = production hardening, P2 = future / nice-to-have.

## Shipped (v0.1.0)

| ID | Feature | Pri | Spec |
|----|---------|-----|------|
| F01 | Document ingestion pipeline | P0 | [F01](specs/F01-ingestion.md) |
| F02 | Retrieval + vector store | P0 | [F02](specs/F02-retrieval.md) |
| F03 | Grounded answers + citations | P0 | [F03](specs/F03-citations.md) |
| F04 | Pluggable providers | P0 | [F04](specs/F04-providers.md) |
| F05 | REST API | P0 | [F05](specs/F05-api.md) |
| F11 | Config + secrets | P0 | [F11](specs/F11-config-secrets.md) |
| F06 | Streaming (SSE) | P1 | [F06](specs/F06-streaming.md) |
| F07 | Caching | P1 | [F07](specs/F07-caching.md) |
| F08 | Auth + rate limiting | P1 | [F08](specs/F08-auth-rate-limit.md) |
| F09 | Observability | P1 | [F09](specs/F09-observability.md) |
| F10 | Evaluation harness | P1 | [F10](specs/F10-eval.md) |
| F12 | Containerization | P1 | [F12](specs/F12-containerization.md) |
| F13 | CI/CD + quality gates | P1 | [F13](specs/F13-cicd.md) |
| F14 | Web UI (non-technical) | P1 | [F14](specs/F14-web-ui.md) |
| F15 | Release notes / What's New | P1 | [F15](specs/F15-release-notes.md) |

## Next (P2 — not yet specced)

| Idea | Why |
|------|-----|
| Hybrid retrieval (BM25 + dense) | better recall on exact figures/codes |
| Re-ranker (cross-encoder) | sharper top-k before generation |
| Per-document upload via UI | let non-technical users add their own files |
| Conversation memory / follow-ups | multi-turn Q&A over the same corpus |
| Answer feedback (👍/👎) + capture | build an eval set from real usage |
| Auth via API gateway / SSO | when multi-tenant |

> When a P2 item gets picked up, write its spec in `specs/` **before** coding.
