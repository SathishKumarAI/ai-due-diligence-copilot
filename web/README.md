# Web UI — AI Due Diligence Copilot

A friendly Next.js front end for non-technical users. Hold a **multi-turn
conversation** with the documents, watch answers **stream** in with clickable
source citations, **upload your own** deal documents, give **👍/👎 feedback**, and
see a **What's New** feed of recent changes — in light or dark mode.

## Run locally

```bash
cd web
cp .env.example .env.local      # point NEXT_PUBLIC_API_BASE_URL at the backend
npm install
npm run dev                     # http://localhost:3000
```

The backend (FastAPI) must be running and reachable at `NEXT_PUBLIC_API_BASE_URL`
(default `http://localhost:8000`). See the project root README for the backend.

## Pages

| Route | What it does |
|-------|--------------|
| `/` | Chat interface: multi-turn Q&A with streaming answers, inline citation chips, document upload, and per-answer feedback |
| `/whats-new` | Plain-language release notes, pulled live from the repo's GitHub Releases |

## Components

`components/` holds the UI: `Chat` (orchestrates the thread, history, and
streaming), `AnswerText` (renders `[n]` chips), `CitationList`, `FeedbackButtons`
(F19), `UploadButton` (F18), `StatusBadge` (polls `/ready`), and `ThemeToggle`.

## Deploy

Deployable to Vercel as-is (root directory `web/`). Set the two
`NEXT_PUBLIC_*` env vars in the Vercel project. The backend can run anywhere
reachable over HTTPS (a container host, Fly, Render, etc.).

## Config

Domain-specific copy (title, accent colour, example questions, repo) lives in
[`lib/config.ts`](lib/config.ts) — the only file that differs between the three
sister projects.
