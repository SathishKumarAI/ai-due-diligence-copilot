"""Multi-dimensional RAG evaluation with Ragas (feature F25).

`run_eval.py` measures two things: did the expected source get retrieved, and does a
single LLM judge call the answer grounded. That is a gate, not a diagnosis — when the
number drops it does not say whether retrieval brought back the wrong chunks, brought
back the right ones and buried them, or brought back the right ones and the model
ignored them.

Ragas separates those:

    faithfulness       is the answer supported by the context it was given?
    context_precision  of the chunks retrieved, how many were actually relevant?
    context_recall     did retrieval find everything the reference answer needs?

Read together they localise a regression. Low recall is a retrieval problem; high recall
with low precision is a ranking problem; good context with low faithfulness is a
generation problem. It also finally uses `expected_answer`, which has sat unused in
qa_dataset.jsonl since the dataset was written.

    python eval/run_ragas.py
    python eval/run_ragas.py --limit 3

Dev-only: ragas lives in requirements-dev.txt and nothing in app/ imports it, so the
shipped image and the runtime dependency surface are unchanged.

No API key is needed. Ragas drives its judge through an OpenAI-compatible client, and
Ollama serves exactly that at /v1, so the judge is the same local model that produced
the answers. That is worth being explicit about: judge and generator being one model
means the scores are self-assessment, and a model is a soft grader of its own output.
Treat these as a relative signal across runs, not an absolute quality claim.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app.config import settings  # noqa: E402
from app.main import build_engine  # noqa: E402

FAITHFULNESS_THRESHOLD = 0.70
CONTEXT_PRECISION_THRESHOLD = 0.70
CONTEXT_RECALL_THRESHOLD = 0.70


def build_judge():  # noqa: ANN201 - ragas type is internal
    """A Ragas judge backed by the local Ollama server over its OpenAI-compatible API.

    AsyncOpenAI, not OpenAI: the collections metrics' ``score()`` is a thin
    ``asyncio.run(ascore(...))`` wrapper, and ascore calls ``llm.agenerate()``, which
    rejects a synchronous client with "Cannot use agenerate() with a synchronous
    client". A sync client fails on every sample rather than at construction.
    """
    from openai import AsyncOpenAI
    from ragas.llms import llm_factory

    client = AsyncOpenAI(
        base_url=f"{settings.ollama_base_url.rstrip('/')}/v1",
        api_key="ollama",  # Ollama ignores this; the client requires something non-empty.
    )
    return llm_factory(settings.ollama_llm_model, provider="openai", client=client)


def main() -> int:
    ap = argparse.ArgumentParser(description="Ragas evaluation over eval/qa_dataset.jsonl")
    ap.add_argument("--limit", type=int, default=None, help="only the first N questions")
    ap.add_argument(
        "--gate",
        action="store_true",
        help="exit non-zero when a score is below its threshold (default: report only)",
    )
    args = ap.parse_args()

    from ragas.metrics.collections import ContextPrecision, ContextRecall, Faithfulness

    dataset_path = Path(__file__).parent / "qa_dataset.jsonl"
    rows = [
        json.loads(line)
        for line in dataset_path.read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]
    if args.limit:
        rows = rows[: args.limit]

    engine = build_engine()
    print(f"provider={settings.provider} model={settings.ollama_llm_model}")
    print(
        f"retrieval={settings.retrieval_mode} rerank={settings.rerank_enabled} top_k={settings.top_k}"
    )
    print(f"Generating answers for {len(rows)} questions…")

    samples = []
    for i, row in enumerate(rows, 1):
        # answer_with_trace gives the answer and the exact chunks behind it in one pass,
        # so the contexts scored are the contexts the model actually saw.
        answer, trace = engine.answer_with_trace(row["question"])
        samples.append(
            {
                "user_input": row["question"],
                "response": answer.answer,
                "retrieved_contexts": [c.snippet for c in trace.retrieved],
                "reference": row["expected_answer"],
            }
        )
        print(f"  {i}/{len(rows)} {row['question'][:60]}")

    judge = build_judge()
    # Scored per sample rather than through ragas.evaluate(): the collections metrics are
    # the current API and evaluate() only accepts the legacy Metric classes. Calling them
    # directly also keeps per-question scores, which is what tells you *which* question
    # regressed rather than only that the mean moved.
    metrics = {
        "faithfulness": Faithfulness(llm=judge),
        "context_precision": ContextPrecision(llm=judge),
        "context_recall": ContextRecall(llm=judge),
    }
    fields = {
        "faithfulness": ("user_input", "response", "retrieved_contexts"),
        "context_precision": ("user_input", "reference", "retrieved_contexts"),
        "context_recall": ("user_input", "retrieved_contexts", "reference"),
    }

    print("\nScoring with Ragas…")
    per_metric: dict[str, list[float]] = {name: [] for name in metrics}
    for i, sample in enumerate(samples, 1):
        line = [f"  {i}/{len(samples)}"]
        for name, metric in metrics.items():
            try:
                result = metric.score(**{f: sample[f] for f in fields[name]})
                value = float(getattr(result, "value", result))
                per_metric[name].append(value)
                line.append(f"{name.split('_')[-1]}={value:.2f}")
            except Exception as exc:  # noqa: BLE001 - one bad sample must not lose the run
                # Print the message, not just the type. The first run of this script
                # showed three columns of ERR(TypeError) and nothing else, which said
                # only that something was wrong, not that the judge had been handed a
                # synchronous client.
                line.append(f"{name.split('_')[-1]}=ERR({type(exc).__name__}: {exc})")
        print(" ".join(line))

    scores = {name: sum(values) / len(values) for name, values in per_metric.items() if values}
    print("\n--- Ragas ---")
    thresholds = {
        "faithfulness": FAITHFULNESS_THRESHOLD,
        "context_precision": CONTEXT_PRECISION_THRESHOLD,
        "context_recall": CONTEXT_RECALL_THRESHOLD,
    }
    below_threshold = False
    unmeasured = False
    for name, threshold in thresholds.items():
        value = scores.get(name)
        if value is None:
            # A metric that produced no score at all is a failure, not a blank. Reporting
            # PASS here would repeat the corpus fetcher's bug: exiting 0 having measured
            # nothing, which reads as success to a human and to CI alike.
            print(f"{name:<18}: NOT MEASURED - every sample errored")
            unmeasured = True
            continue
        passed = value >= threshold
        below_threshold |= not passed
        print(f"{name:<18}: {value:.2f}  (threshold {threshold:.2f}) {'OK' if passed else 'FAIL'}")

    # Two different failures, deliberately not collapsed into one exit code.
    #
    # A score below threshold is a *quality* signal, and today it is not a trustworthy
    # one: the corpus is four synthetic documents and the judge is the same llama3.1:8b
    # that wrote the answers, so it is grading itself. Faithfulness 0.58 against a 0.70
    # bar is not evidence the pipeline is broken. The tempting fix was to lower the
    # thresholds until they went green, which destroys the only reason to keep the
    # numbers at all. So the thresholds stay at 0.70 and the run is informational unless
    # --gate is passed. Nothing wires --gate into CI until a real corpus exists.
    #
    # A metric that could not be measured is a *harness* failure - the judge is
    # misconfigured, the model is not running, the API changed - and that is never a soft
    # signal. It exits non-zero with or without --gate, because "measured nothing" must
    # not be indistinguishable from "measured fine".
    if unmeasured:
        print("\nFAIL - at least one metric could not be measured (harness error)")
        return 1
    if below_threshold:
        if args.gate:
            print("\nFAIL - below threshold, and --gate was passed")
            return 1
        print(
            "\nBELOW THRESHOLD (informational; exit 0)\n"
            "  Judge and generator are the same model on a 4-document corpus, so these\n"
            "  scores are self-assessment. Pass --gate to make them blocking."
        )
        return 0
    print("\nPASS")
    return 0


if __name__ == "__main__":
    sys.exit(main())
