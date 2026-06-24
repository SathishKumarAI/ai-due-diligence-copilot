# AI Due Diligence Copilot

> A production-style **RAG** service that answers investor due-diligence questions
> over deal documents and **cites the source passage for every claim**. Runs free
> and offline by default (Ollama + open-source embeddings); swap one env var for
> Claude. Ships with a friendly web UI for non-technical users.

![status](https://img.shields.io/badge/status-portfolio-blue) ![license](https://img.shields.io/badge/license-MIT-green)

## What it does

Point it at a folder of documents (pitch decks, 10-Ks, term sheets, contracts).
Ask a question in plain language. It retrieves the most relevant passages and asks
an LLM to answer **using only those passages**, returning the answer plus the
sources it relied on — so every claim is traceable. It refuses to answer when the
documents don't cover the question.

## Architecture

```
                ┌──────────────┐
  documents ──► │   ingest     │ load → chunk → embed → Chroma (vector DB)
                └──────────────┘
                       │
  question ──► retrieve top-k ──► prompt + LLM ──► answer + citations[]
                       ▲                                   │
                       └──────────── web UI (Next.js) ◄────┘
```

- **Backend:** FastAPI (`/v1/ask`, `/v1/ask/stream`, `/v1/ingest`, `/v1/sources`,
  `/health`, `/ready`, `/metrics`)
- **Models (`PROVIDER` switch):** `ollama` (llama3.1 + `bge-small-en-v1.5`, default,
  free) or `claude` (claude-opus-4-8 + Voyage `voyage-3.5`)
- **Frontend:** Next.js app in [`web/`](web/) — Ask page + "What's New" page
- **Quality:** eval suite (hit-rate + faithfulness), pytest (offline), Docker, CI

See [`docs/`](docs/) for the full kit: [architecture](docs/ARCHITECTURE.md),
[feature specs](docs/specs/), [security](docs/SECURITY.md),
[runbook](docs/RUNBOOK.md), [definition of done](docs/DEFINITION-OF-DONE.md).

## Quick start (backend)

```bash
cp .env.example .env                 # defaults to the free Ollama provider
pip install -r requirements.txt
ollama pull llama3.1:8b              # one-time, for the default provider
python -m app.ingest                 # build the vector index from data/
uvicorn app.main:app --reload        # http://localhost:8000  (/docs for OpenAPI)

curl -s localhost:8000/v1/ask -H 'content-type: application/json' \
  -d '{"question":"What are the main risks for this company?"}'
```

Use Claude instead: set `PROVIDER=claude`, `ANTHROPIC_API_KEY`, `VOYAGE_API_KEY`.

## Quick start (frontend)

```bash
cd web && cp .env.example .env.local && npm install && npm run dev   # :3000
```

## Develop

```bash
make setup      # install dev deps
make test       # offline tests (fake provider, no network)
make lint       # ruff
make typecheck  # mypy
make eval       # retrieval hit-rate + faithfulness (needs a provider)
make docker     # api + ollama via docker compose
```

## Disclaimer

Informational analysis, not investment advice. The bundled `data/` is **synthetic**.

## License

MIT — see [LICENSE](LICENSE).
