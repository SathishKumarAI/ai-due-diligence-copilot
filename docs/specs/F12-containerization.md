# Feature Spec — F12 Containerization

## Summary
A multi-stage, non-root Docker image for the API, plus a compose stack that includes
an Ollama daemon.

## Problem / why
"Runs on my machine" isn't deployable. A container makes the service portable and the
local stack reproducible.

## Users & context
Anyone deploying or running the full stack locally.

## Behaviour (acceptance criteria)
- WHEN the image is built THEN dependencies install in a builder stage and the runtime
  stage runs as a non-root user.
- WHEN the container runs THEN the API serves on port 8000 with a `HEALTHCHECK`.
- WHEN `docker compose up` runs THEN the API and an `ollama` service start and can talk.

## Rules / logic
- `python:3.12-slim` base; deps copied from the builder `--prefix`.
- `HEALTHCHECK` hits `/health`. Compose mounts `chroma_db/` and a model volume.

## Out of scope (for now)
- Multi-arch images, image signing, k8s manifests.

## Data touched
- Reads: source + `data/`. Writes: container `chroma_db/` (volume-mounted).

## Edge cases
- First run needs `ollama pull llama3.1:8b` and an `ingest` inside the stack (RUNBOOK).

## Done when
- `docker build` succeeds (CI builds it); `docker compose up` serves `/health`.
