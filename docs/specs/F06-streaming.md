# Feature Spec — F06 Streaming responses (SSE)

## Summary
Stream the answer token-by-token over Server-Sent Events, then deliver citations.

## Problem / why
For long answers, waiting for the whole response feels slow. Streaming shows progress
immediately — important for a friendly UX.

## Users & context
`POST /v1/ask/stream`, consumed by the UI (or any SSE client).

## Behaviour (acceptance criteria)
- WHEN streaming starts THEN `token` events arrive as the model generates.
- WHEN generation finishes THEN one `citations` event carries the source list (JSON),
  then a `done` event closes the stream.
- WHEN nothing is retrieved THEN a single guardrail token is sent, then empty citations.

## Rules / logic
- `RagEngine.stream` yields `("token", str)` then `("citations", [...])`.
- Uses `sse_starlette.EventSourceResponse`; citations are collected from the streamed
  text using the same marker-mapping as F03.

## Out of scope (for now)
- Mid-stream cancellation, partial-citation streaming.

## Data touched
- Reads: the index. Writes: none (streamed answers are not cached).

## Edge cases
- Client disconnects mid-stream · empty retrieval · provider that doesn't stream
  (LangChain falls back to a single chunk).

## Done when
- `RagEngine.stream` yields tokens then a citations tuple (covered via the fake chat
  model in tests); the UI renders a streamed answer.
