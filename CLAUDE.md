# CLAUDE.md

## Project overview
AI Due Diligence Copilot — a RAG service that answers investor due-diligence
questions over deal documents (pitch decks, 10-Ks, term sheets) and **cites the
source passage** for every claim. FastAPI backend + Next.js frontend.

## Tech stack
- Python 3.11+, LangChain, Chroma (local persistent vector DB)
- Models via a `PROVIDER` switch: `ollama` (llama3.1 + HF `bge-small-en-v1.5`,
  default/free) or `claude` (claude-opus-4-8 + Voyage `voyage-3.5`)
- API: FastAPI + uvicorn. Frontend: Next.js (App Router, TypeScript) in `web/`
- Tests: pytest — run with `pytest` (offline; fake provider, no network)

## Key concepts (see GLOSSARY.md)
- chunk — a slice of a document that gets embedded and retrieved
- citation — a `[n]` marker in the answer mapped to a real retrieved chunk
- provider — the swappable model backend (`ollama` | `claude`)
- grounding — answering only from retrieved passages, never invented facts

## Existing features
See FEATURES.md before building anything new — don't duplicate or break it.
Specs are the source of truth: `docs/specs/F01..F15`.

## Conventions
- Match nearby code; follow the provider-seam pattern (`app/providers.py`) — depend
  on LangChain interfaces, never a concrete vendor class.
- Do NOT add dependencies without asking.
- Python: 4-space indent, type hints, ruff-formatted (`make fmt`). snake_case.
- New logic requires unit tests, including no-data and edge cases. Tests stay
  offline — inject fakes, never hit a network/model in CI.
- Secrets only via env / `.env` (gitignored). Never hardcode keys.

## How features are briefed
Write/READ the feature spec in `docs/specs/` first (the user's Feature Spec form).
Explore + propose a plan before code; state behaviour as "WHEN X THEN Y"; define
how to verify done against `docs/DEFINITION-OF-DONE.md`.

## Commands
- Setup: `make setup`   Test: `make test`   Lint: `make lint`   Types: `make typecheck`
- Ingest: `python -m app.ingest`   Run API: `make run`   Eval: `make eval`
- Frontend: `cd web && npm run dev`
