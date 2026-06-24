# Feature Spec — F11 Config + secrets

## Summary
All runtime configuration comes from environment variables (with sane defaults), and
secrets are never committed.

## Problem / why
Hardcoded config and committed secrets are the two most common production mistakes.
One typed settings object keeps config discoverable and safe.

## Users & context
Operators set env vars / `.env`; every module reads `settings`.

## Behaviour (acceptance criteria)
- WHEN the app starts THEN settings load from env / `.env` via pydantic-settings.
- WHEN a value isn't set THEN the documented default applies.
- WHEN a secret is needed (`claude` path) THEN it's read from env, never a literal.
- WHEN `.env` is present THEN it's gitignored; `.env.example` lists every key.

## Rules / logic
- `app/config.py` is the single `Settings` source; `auth_required` derives from `api_key`.
- Types validated by pydantic (e.g. `provider` is a `Literal["ollama","claude"]`).

## Out of scope (for now)
- Secret managers (Vault/SSM); per-environment config files beyond `.env`.

## Data touched
- Reads: env / `.env`. Writes: none.

## Edge cases
- Unknown env keys ignored (`extra="ignore"`) · invalid `provider` → validation error.

## Done when
- App runs key-free on the default provider; `.env.example` documents all keys;
  `.env` is gitignored.
