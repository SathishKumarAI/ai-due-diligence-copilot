# Contributing

Thanks for your interest! This is a portfolio project, but PRs and issues are welcome.

## Workflow

1. **Read the spec first.** Behaviour lives in [`docs/specs/`](docs/specs/). If you're
   changing behaviour, update (or add) the spec in the same PR.
2. **Branch** off `main`: `git checkout -b feat/<short-name>`.
3. **Develop** following [`CLAUDE.md`](CLAUDE.md) conventions and the provider seam
   (`app/providers.py`) — depend on LangChain interfaces, never a vendor class.
4. **Test offline.** Add unit tests (including no-data / edge cases). Tests must not
   hit a network or download a model — inject fakes (see `tests/conftest.py`).
5. **Pass the gates:** `make lint && make typecheck && make test`.
6. **Update the changelog** under `## [Unreleased]` in [`CHANGELOG.md`](CHANGELOG.md).
7. **Open a PR.** CI runs ruff, mypy, pytest, and a Docker build.

## Definition of Done

A change is done only when it meets [`docs/DEFINITION-OF-DONE.md`](docs/DEFINITION-OF-DONE.md).

## Commit style

Conventional-ish: `feat:`, `fix:`, `docs:`, `test:`, `chore:`. Keep the subject ≤ 50
chars; explain the *why* in the body when it isn't obvious.

## Reporting security issues

See [`docs/SECURITY.md`](docs/SECURITY.md). Don't open a public issue for a vulnerability.
