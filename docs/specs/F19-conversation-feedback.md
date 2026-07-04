# Feature Spec — F19 Conversation memory + answer feedback

## Summary
Two related capabilities: (a) multi-turn follow-up questions that understand the
prior exchange, and (b) 👍/👎 feedback capture on answers to seed a real eval set.

## Problem / why
Users naturally ask follow-ups ("and its margin?") that are meaningless without the
previous turn. And the team needs ground-truth on which answers were good — captured
from real usage, not guessed.

## Users & context
Web UI users (chat-style thread + thumb buttons); programmatic callers via the
extended `/v1/ask` request and a new `/v1/feedback` endpoint.

## Behaviour (acceptance criteria)
### Conversation memory
- WHEN `/v1/ask` includes `history` (prior user/assistant turns) THEN the engine
  condenses the new question + history into a standalone query before retrieval.
- WHEN `history` is empty/absent THEN behaviour is identical to F03 (single turn).
- WHEN condensing fails or the history is irrelevant THEN the original question is
  used (no regression).

### Feedback
- WHEN a user submits feedback THEN `{question, answer, rating, comment?}` is appended
  to `data/feedback.jsonl` with a UTC timestamp, and the API returns `{ok: true}`.
- WHEN `rating` is not `up`/`down` THEN the API returns 422.

## Rules / logic
- Condensing: a small LLM call rewrites "history + follow-up" into one self-contained
  question; only the rewritten query is embedded/retrieved. The original question is
  still what the answer addresses and what gets cached/returned.
- Caching: the cache key includes a hash of `history` so follow-ups don't collide
  with the same words asked cold.
- Feedback store: append-only JSONL via the stdlib (no new dependency, no DB).

## Out of scope (for now)
- Server-side conversation persistence / accounts (history is client-supplied).
- Automated retraining or eval-set promotion from feedback (manual for now).

## Data touched
- Reads: client-supplied history. Writes: `data/feedback.jsonl`.

## Edge cases
- Long history (truncated to last N turns) · empty comment · condense LLM echoes the
  question (fine) · concurrent feedback writes (append mode, one line each).

## Done when
- A follow-up that omits the subject is answered correctly using history, feedback
  rows are persisted, and unit tests cover condense-with-history, single-turn
  passthrough, feedback append, and bad-rating rejection.
