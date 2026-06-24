# Feature Spec — F03 Grounded answers with citations

## Summary
Answer the question using only the retrieved passages, and return the sources each
claim drew on as `[n]` citations.

## Problem / why
An ungrounded or uncited answer can't be trusted for a high-stakes decision. Citations
make every claim traceable to a real source passage.

## Users & context
The core value of the product; every `/v1/ask` returns this.

## Behaviour (acceptance criteria)
- WHEN passages are retrieved THEN they're numbered `[1..k]` and the model is told to
  answer only from them and cite with `[n]`.
- WHEN the answer cites `[2]` THEN the response includes a citation for marker 2 with
  the real `source`, `page`, and a snippet of chunk 2.
- WHEN the model emits no markers THEN all retrieved chunks are returned as sources
  (still traceable).
- WHEN nothing is retrieved THEN the answer is "The provided documents do not cover
  this." and `citations` is empty — the LLM is not called.

## Rules / logic
- Citations are built from retrieval **metadata**, never parsed from model-invented
  text (see ADR-0002). Marker→chunk mapping by index.
- System prompt enforces grounding, no invented figures, and risk-flagging.

## Out of scope (for now)
- Sub-sentence character-offset citations; native provider citation APIs.

## Data touched
- Reads: retrieved chunks. Writes: answer cache (F07).

## Edge cases
- Out-of-range marker (model cites `[9]` with k=5) → ignored. Duplicate markers →
  de-duplicated. No markers → fallback to all chunks.

## Done when
- `tests/test_citations.py` passes (marker mapping, fallback, no-data guardrail).
- Eval faithfulness ≥ 70%.
