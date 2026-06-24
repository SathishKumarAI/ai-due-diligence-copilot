# Feature Spec — F14 Web UI (non-technical)

## Summary
A Next.js app that lets a non-technical user ask a question and read an answer with
clickable source citations — no setup.

## Problem / why
The service is only useful if a non-engineer can use it. The UI removes all friction
between "I have a question" and "here's a sourced answer".

## Users & context
Non-technical users (investors, analysts) opening the deployed URL.

## Behaviour (acceptance criteria)
- WHEN the page loads THEN there's a question box and clickable **example questions**.
- WHEN a question is submitted THEN the answer renders with source cards (marker,
  filename, page, snippet).
- WHEN the question is < 3 chars THEN submission is ignored (matches backend validation).
- WHEN the backend is unreachable THEN a friendly error names the backend URL — never
  a stack trace.
- WHEN a request is in flight THEN the button shows a loading state.

## Rules / logic
- `web/lib/config.ts` holds the per-project copy (title, accent, examples, repo) — the
  only file that changes between sister projects.
- `web/lib/api.ts::ask` calls `POST /v1/ask`; sends `X-API-Key` if configured.

## Out of scope (for now)
- File upload, multi-turn chat, auth UI beyond an env-provided key.

## Data touched
- Reads: backend `/v1/ask`. Writes: none (stateless UI).

## Edge cases
- Empty/whitespace question · backend 401/429/503 surfaced as readable messages ·
  answer with zero citations (sources section hidden).

## Done when
- `web/` builds; the Ask page renders an answer + citations against a running backend.
