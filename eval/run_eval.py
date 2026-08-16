"""Evaluation harness (feature F10).

Two metrics over eval/qa_dataset.jsonl:
  - retrieval hit-rate: did the expected source appear in the top-k chunks?
  - answer faithfulness: LLM-as-judge — is the answer grounded in retrieved context?

Exits non-zero if either metric falls below its threshold, so CI can gate on it.
Requires a built index and a reachable provider (Ollama or Claude).

    python eval/run_eval.py

The engine comes from ``app.main.build_engine`` — the same constructor the API uses —
so the numbers describe the retrieval stack that actually ships. An earlier version
built ``RagEngine`` here with no retriever and no reranker, which silently scored plain
dense retrieval no matter what RETRIEVAL_MODE said; the config banner below exists so a
mismatch is visible in the output rather than implied.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

# Running this as a script puts eval/ on sys.path, not the repo root, so `import app`
# raises ModuleNotFoundError. Both the Makefile target and the docstring above invoke it
# that way, so bootstrap the root rather than change the documented command.
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app.config import settings  # noqa: E402
from app.main import build_engine  # noqa: E402
from scripts.run_log import record_run  # noqa: E402

HIT_RATE_THRESHOLD = 0.7
FAITHFULNESS_THRESHOLD = 0.7

JUDGE_PROMPT = (
    "You are grading a RAG answer. Given the CONTEXT and the ANSWER, reply with a "
    "single word: GROUNDED if every factual claim in the answer is supported by the "
    "context, or UNSUPPORTED otherwise.\n\nCONTEXT:\n{context}\n\nANSWER:\n{answer}"
)


def is_grounded(verdict: str) -> bool:
    """Parse the judge's verdict, failing closed.

    A bare ``"GROUNDED" in verdict`` also matched "NOT GROUNDED", so a chatty judge
    scored its own rejections as passes. Anything that is not an unambiguous GROUNDED
    now counts against the metric.
    """
    v = verdict.strip().upper()
    if "UNSUPPORTED" in v or "NOT GROUNDED" in v:
        return False
    return "GROUNDED" in v


def main() -> int:
    ap = argparse.ArgumentParser(description="Evaluate retrieval and faithfulness.")
    ap.add_argument(
        "--dataset",
        type=Path,
        default=Path(__file__).parent / "qa_dataset.jsonl",
        help="JSONL dataset (default eval/qa_dataset.jsonl)",
    )
    args = ap.parse_args()

    rows = [
        json.loads(line)
        for line in args.dataset.read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]

    engine = build_engine()
    llm = engine.llm

    hits = 0
    scored_for_retrieval = 0
    grounded = 0
    print(f"Running {len(rows)} eval questions")
    print(
        f"  provider={settings.provider} model={settings.ollama_llm_model} "
        f"retrieval={settings.retrieval_mode} rerank={settings.rerank_enabled} "
        f"top_k={settings.top_k}\n"
    )
    for row in rows:
        q = row["question"]
        expected_src = row.get("expected_source")

        # One pass: the hit-rate, the judged context and the answer all come from the
        # same retrieval, so the metrics cannot describe a different draw than the one
        # that produced the answer.
        answer, trace = engine.answer_with_trace(q)
        retrieved_srcs = {c.source for c in trace.retrieved}

        # A row with no expected_source is not a retrieval failure - it is a question
        # that never claimed which document should answer it. Ragas-generated sets
        # (scripts/generate_testset.py) carry the context text but not the file it came
        # from, so counting them as misses would report 0% hit-rate on a perfectly
        # healthy pipeline. They are excluded from the hit-rate and still judged for
        # faithfulness.
        if expected_src is None:
            flag = "n/a "
        else:
            hit = expected_src in retrieved_srcs
            hits += hit
            scored_for_retrieval += 1
            flag = "OK  " if hit else "MISS"

        verdict = llm.invoke(
            JUDGE_PROMPT.format(context=trace.user_prompt, answer=answer.answer)
        ).content
        judged = is_grounded(str(verdict))
        grounded += judged

        gflag = "OK  " if judged else "FAIL"
        print(f"  [retrieval {flag}] [faithful {gflag}] {q}")

    n = len(rows)
    # 1.0 rather than 0.0 when nothing carried an expected_source: a metric measured over
    # zero samples must not masquerade as a perfect or a catastrophic score. The count is
    # printed alongside so the denominator is never implied.
    hit_rate = hits / scored_for_retrieval if scored_for_retrieval else 1.0
    faithfulness = grounded / n
    print("\n--- Results ---")
    print(
        f"Retrieval hit-rate : {hit_rate:.0%}  (threshold {HIT_RATE_THRESHOLD:.0%})"
        f"  [{hits}/{scored_for_retrieval} rows with a known source]"
    )
    print(f"Faithfulness       : {faithfulness:.0%}  (threshold {FAITHFULNESS_THRESHOLD:.0%})")
    if not scored_for_retrieval:
        print("  note: no row carried expected_source, so retrieval was not measured.")

    ok = hit_rate >= HIT_RATE_THRESHOLD and faithfulness >= FAITHFULNESS_THRESHOLD

    # Recorded whether it passed or failed. A history that only keeps the good runs
    # cannot show a regression, which is the only thing the history is for.
    record_run(
        "eval",
        {"hit_rate": round(hit_rate, 3), "faithfulness": round(faithfulness, 3)},
        extra={
            "questions": n,
            "passed": ok,
            "dataset": args.dataset.name,
            "retrieval_scored": scored_for_retrieval,
        },
    )

    print("\nPASS" if ok else "\nFAIL")
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
