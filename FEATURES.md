# Features (built)

Read this before adding anything — don't duplicate or break existing behaviour.
Each feature has a spec in [`docs/specs/`](docs/specs/) (the source of truth).

| ID | Feature | Status | Spec |
|----|---------|--------|------|
| F01 | Document ingestion pipeline | ✅ | [F01](docs/specs/F01-ingestion.md) |
| F02 | Retrieval + vector store | ✅ | [F02](docs/specs/F02-retrieval.md) |
| F03 | Grounded answers with citations | ✅ | [F03](docs/specs/F03-citations.md) |
| F04 | Pluggable model providers | ✅ | [F04](docs/specs/F04-providers.md) |
| F05 | REST API | ✅ | [F05](docs/specs/F05-api.md) |
| F06 | Streaming responses (SSE) | ✅ | [F06](docs/specs/F06-streaming.md) |
| F07 | Caching (answer + embedding) | ✅ | [F07](docs/specs/F07-caching.md) |
| F08 | Auth + rate limiting | ✅ | [F08](docs/specs/F08-auth-rate-limit.md) |
| F09 | Observability | ✅ | [F09](docs/specs/F09-observability.md) |
| F10 | Evaluation harness | ✅ | [F10](docs/specs/F10-eval.md) |
| F11 | Config + secrets | ✅ | [F11](docs/specs/F11-config-secrets.md) |
| F12 | Containerization | ✅ | [F12](docs/specs/F12-containerization.md) |
| F13 | CI/CD + quality gates | ✅ | [F13](docs/specs/F13-cicd.md) |
| F14 | Web UI (non-technical) | ✅ | [F14](docs/specs/F14-web-ui.md) |
| F15 | Release notes / What's New | ✅ | [F15](docs/specs/F15-release-notes.md) |
| F16 | Hybrid retrieval (BM25 + dense, RRF) | ✅ | [F16](docs/specs/F16-hybrid-retrieval.md) |
| F17 | Cross-encoder re-ranker | ✅ | [F17](docs/specs/F17-reranker.md) |
| F18 | Per-document upload via UI | ✅ | [F18](docs/specs/F18-upload.md) |
| F19 | Conversation memory + answer feedback | ✅ | [F19](docs/specs/F19-conversation-feedback.md) |
| F20 | OCR ingestion (scanned PDF + images, local Tesseract) | ✅ | [F20](docs/specs/F20-ocr.md) |
| F21 | Cleaning pipeline + hardened prompts | ✅ | [F21](docs/specs/F21-cleaning-prompts.md) |
| F22 | Open-access corpus fetch (SEC EDGAR) | ✅ | [F22](docs/specs/F22-corpus.md) |
| F23 | Pipeline trace + introspection UI | ✅ | [F23](docs/specs/F23-trace-introspection.md) |

Understand the pipeline: [`docs/HOW-RAG-WORKS.md`](docs/HOW-RAG-WORKS.md) ·
[`docs/INGESTION.md`](docs/INGESTION.md) · [`docs/ARCHITECTURE.md`](docs/ARCHITECTURE.md).

Backlog and future ideas: [`docs/BACKLOG.md`](docs/BACKLOG.md).
