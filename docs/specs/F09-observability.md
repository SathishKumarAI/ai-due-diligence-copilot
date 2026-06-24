# Feature Spec — F09 Observability

## Summary
Structured JSON logs with a request id, plus Prometheus metrics for traffic, latency,
RAG stage timings, and cache hits.

## Problem / why
You can't operate what you can't see. Logs + metrics make latency, errors, and cache
effectiveness visible.

## Users & context
Operators reading logs/dashboards; `/metrics` scraped by Prometheus.

## Behaviour (acceptance criteria)
- WHEN any request is handled THEN a JSON log line is emitted with `request_id`, path,
  method, status, and `duration_ms`.
- WHEN a response is returned THEN it carries an `x-request-id` header (echoing an
  incoming one if present).
- WHEN `/metrics` is scraped THEN it exposes `rag_requests_total`,
  `rag_request_latency_seconds`, `rag_ask_stage_seconds{stage}`, `rag_cache_hits_total`.
- WHEN an `/v1/ask` runs THEN retrieve/generate stage timings are recorded.

## Rules / logic
- `structlog` JSON renderer; `RequestContextMiddleware` binds/clears contextvars.
- Prometheus counters/histograms in `app/observability.py`.

## Out of scope (for now)
- Distributed tracing (OpenTelemetry), log shipping, alerting rules.

## Data touched
- Reads: request metadata. Writes: stdout logs + in-process metric registries.

## Edge cases
- Exceptions still increment a 500 counter and log a stack trace · contextvars cleared
  even on error (no request-id leakage across requests).

## Done when
- `tests/test_api.py::test_metrics_endpoint_exposes_prometheus` passes; logs are JSON.
