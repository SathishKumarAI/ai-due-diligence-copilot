# Feature Spec — F08 Auth + rate limiting

## Summary
Optionally require an API key on `/v1/*`, and rate-limit requests per key/IP.

## Problem / why
A deployed service needs to bound who can call it and how fast, without forcing keys
on local/dev use.

## Users & context
Operators set `API_KEY` and `RATE_LIMIT_PER_MIN`; the UI sends `X-API-Key` if set.

## Behaviour (acceptance criteria)
- WHEN `API_KEY` is set AND a `/v1/*` request omits/ mismatches `X-API-Key` THEN 401.
- WHEN `API_KEY` is set AND the header matches THEN the request proceeds.
- WHEN `API_KEY` is empty THEN `/v1/*` is open (local/dev default).
- WHEN a caller exceeds `RATE_LIMIT_PER_MIN` THEN 429.
- WHEN a caller is under the limit THEN requests pass; tokens refill over time.
- Health/ready/metrics are always unauthenticated.

## Rules / logic
- `require_api_key` dependency: no-op unless `settings.auth_required`.
- `TokenBucket` per key (or client IP if no key); capacity = limit, refill = limit/60/s.

## Out of scope (for now)
- Multiple keys / scopes, JWT/SSO, distributed rate limiting (single-process only).

## Data touched
- Reads: headers, config. Writes: in-memory bucket state.

## Edge cases
- No client IP (treated as "anonymous") · clock handled via monotonic time · burst then
  idle (refills).

## Done when
- `tests/test_api.py::test_auth_required_when_api_key_set` passes; 429 path verified.
