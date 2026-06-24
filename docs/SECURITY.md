---
title: Security
description: Secrets, auth, prompt-injection, and data handling. Tier: Growing.
sidebar_position: 7
---

# Security

> Scaled to the stakes: this serves **synthetic** documents and holds no real PII or
> money, so there's no threat model or compliance doc. It does cover the real
> surface — secrets, auth, prompt-injection, and dependency hygiene.

## Reporting a vulnerability

Email the maintainer (see GitHub profile) rather than opening a public issue. Expect
an acknowledgement within a few days.

## Secrets

- All secrets come from env / `.env` (gitignored). `.env.example` documents every key
  with no real values.
- `detect-private-key` runs in pre-commit; CI never echoes secrets.
- The Claude path needs `ANTHROPIC_API_KEY` + `VOYAGE_API_KEY`; the default Ollama
  path needs none.

## Auth & abuse

- `API_KEY` (when set) gates all `/v1/*` routes via an `X-API-Key` header; unset = open
  (intended for local/dev). Set it in any shared deployment.
- Token-bucket rate limiting per key (or client IP) — default 60/min — caps abuse.
- CORS origins are configurable; lock them down in production.

## Prompt injection

Retrieved document text is **untrusted input.** The system prompt instructs the model
to treat passages as data to summarize, to answer only from them, and to refuse when
they don't cover the question. Citations are derived from retrieval **metadata**, not
from anything the model writes, so a malicious document cannot forge a source path.
This mitigates but does not eliminate injection — don't ingest untrusted documents
into a deployment that can take consequential actions (this service only reads).

## Data handling

- Documents are embedded locally into Chroma; with the Ollama provider nothing leaves
  the machine. With the Claude provider, document text is sent to Anthropic/Voyage.
- The bundled corpus is synthetic. Do not commit real confidential deal documents.

## Dependencies

- Pinned ranges in `requirements*.txt`; review before bumping.
- CI builds the Docker image so supply-chain breakage surfaces early.
