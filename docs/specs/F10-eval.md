# Feature Spec — F10 Evaluation harness

## Summary
Measure RAG quality on a labelled Q&A set: retrieval hit-rate and answer faithfulness.
Fail the build if either drops below threshold.

## Problem / why
"The answers seem good" isn't a bar. Eval turns quality into a number CI can gate on.

## Users & context
Developers run `make eval`; CI runs it where a provider is available.

## Behaviour (acceptance criteria)
- WHEN `eval/run_eval.py` runs THEN for each question it checks whether the expected
  source is in the top-k (hit-rate) and judges whether the answer is grounded in the
  retrieved context (faithfulness, LLM-as-judge).
- WHEN hit-rate ≥ 70% AND faithfulness ≥ 70% THEN it prints PASS and exits 0.
- WHEN either is below threshold THEN it prints FAIL and exits non-zero.

## Rules / logic
- Dataset: `eval/qa_dataset.jsonl` rows `{question, expected_answer, expected_source}`.
- Judge: the same LLM scores `GROUNDED`/`UNSUPPORTED` given context + answer.
- Thresholds are constants at the top of the script.

## Out of scope (for now)
- Answer-correctness vs gold answer; latency/cost budgets; regression history.

## Data touched
- Reads: the index + `qa_dataset.jsonl`. Writes: stdout report; exit code.

## Edge cases
- Missing index → clear failure · judge returns unexpected text → treated as not grounded.

## Done when
- The script runs against a provider and reports both metrics with a pass/fail exit code.
