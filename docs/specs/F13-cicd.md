# Feature Spec — F13 CI/CD + quality gates

## Summary
On every push/PR, run lint, type-check, offline tests, and a Docker build as gates.

## Problem / why
"Done" must mean "the gates are green", not "the agent said so". CI enforces the bar
automatically.

## Users & context
Every contributor; the GitHub Actions runner.

## Behaviour (acceptance criteria)
- WHEN code is pushed to `main` or a PR opens THEN CI runs `ruff check`,
  `ruff format --check`, `mypy app`, and `pytest`.
- WHEN any gate fails THEN the workflow fails (red check).
- WHEN the quality job passes THEN a Docker build job runs.
- Tests run **offline** — no provider, no model download (fakes).

## Rules / logic
- `.github/workflows/ci.yml`: `quality` job then `docker` job (`needs: quality`).
- Local parity via `make lint`, `make typecheck`, `make test`; pre-commit mirrors lint.

## Out of scope (for now)
- Deploy-on-merge (CD), the eval gate in hosted CI (needs a provider), release automation.

## Data touched
- Reads: repo. Writes: CI status checks.

## Edge cases
- Dependency install failure surfaces in CI · format drift caught by `--check`.

## Done when
- CI is green on a clean checkout; `make lint && make typecheck && make test` pass locally.
