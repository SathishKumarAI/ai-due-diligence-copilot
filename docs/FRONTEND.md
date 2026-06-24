---
title: Frontend approach
description: How non-technical users interact with the service, and why. Tier: Growing.
sidebar_position: 9
---

# Frontend approach

> The audience is **non-technical**: they should open a URL, type a question in plain
> language, and read an answer with sources — no setup, no jargon.

## Context / Why

A RAG service is only useful if a non-engineer can use it. The UI's whole job is to
make "ask a question, see a trustworthy answer" effortless, and to show *what changed*
in language anyone can read.

## Decision

A **separate Next.js app** in [`web/`](../web/) (App Router, TypeScript, Tailwind),
talking to the FastAPI backend over `NEXT_PUBLIC_API_BASE_URL`. Deployable to Vercel.

Two pages:

| Page | For the user |
|------|--------------|
| `/` (Ask) | A big text box, **example questions** to click, and an answer card with **source chips** (filename + page + snippet) so every claim is traceable. |
| `/whats-new` | Plain-language updates, newest first (see [changelog strategy](CHANGELOG-STRATEGY.md)). |

### Why not the alternatives
- **Embedded HTML in FastAPI** — simplest, but a real Next.js app is the portfolio
  signal and deploys cleanly to Vercel.
- **Streamlit** — fast, but a separate Python process and less "product web app".

## How it works

- `web/lib/config.ts` — the only file that differs per project (title, accent,
  examples, repo). Swap it to re-skin for another domain.
- `web/lib/api.ts` — `ask()` calls `POST /v1/ask`; `fetchReleases()` reads GitHub
  Releases for the What's New feed.
- Answers render with citation chips; errors tell the user to check the backend URL.

## UX principles (non-technical first)

1. **Example questions** remove the blank-page problem.
2. **Sources visible by default** — trust comes from traceability, not a confident tone.
3. **Plain language** everywhere; the finance disclaimer is always in the footer.
4. **Graceful failure** — a clear "is the backend running?" message, never a stack trace.

## Gotchas

- The backend must allow the UI origin (CORS) — see `app/main.py`.
- For a deployed UI, set `API_KEY` on the backend and `NEXT_PUBLIC_API_KEY` on the UI.
