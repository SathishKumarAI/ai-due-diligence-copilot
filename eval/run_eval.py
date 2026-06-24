"""Evaluation harness (feature F10).

Two metrics over eval/qa_dataset.jsonl:
  - retrieval hit-rate: did the expected source appear in the top-k chunks?
  - answer faithfulness: LLM-as-judge — is the answer grounded in retrieved context?

Exits non-zero if either metric falls below its threshold, so CI can gate on it.
Requires a built index and a reachable provider (Ollama or Claude).

    python eval/run_eval.py
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

from app.cache import wrap_embeddings
from app.config import settings
from app.ingest import load_index
from app.providers import get_embeddings, get_llm
from app.rag import RagEngine

HIT_RATE_THRESHOLD = 0.7
FAITHFULNESS_THRESHOLD = 0.7

JUDGE_PROMPT = (
    "You are grading a RAG answer. Given the CONTEXT and the ANSWER, reply with a "
    "single word: GROUNDED if every factual claim in the answer is supported by the "
    "context, or UNSUPPORTED otherwise.\n\nCONTEXT:\n{context}\n\nANSWER:\n{answer}"
)


def main() -> int:
    dataset = Path(__file__).parent / "qa_dataset.jsonl"
    rows = [json.loads(line) for line in dataset.read_text().splitlines() if line.strip()]

    embeddings = wrap_embeddings(get_embeddings(settings), settings)
    store = load_index(settings, embeddings)
    llm = get_llm(settings)
    engine = RagEngine(store, llm, top_k=settings.top_k, provider=settings.provider)

    hits = 0
    grounded = 0
    print(f"Running {len(rows)} eval questions (provider={settings.provider})\n")
    for row in rows:
        q, expected_src = row["question"], row["expected_source"]
        docs = engine._retrieve(q, settings.top_k)
        retrieved_srcs = {d.metadata.get("source") for d in docs}
        hit = expected_src in retrieved_srcs
        hits += hit

        result = engine.answer(q, settings.top_k)
        context = "\n\n".join(d.page_content for d in docs)
        verdict = llm.invoke(
            JUDGE_PROMPT.format(context=context, answer=result.answer)
        ).content
        is_grounded = "GROUNDED" in str(verdict).upper()
        grounded += is_grounded

        flag = "✓" if hit else "✗"
        gflag = "✓" if is_grounded else "✗"
        print(f"  [retrieval {flag}] [faithful {gflag}] {q}")

    n = len(rows)
    hit_rate = hits / n
    faithfulness = grounded / n
    print("\n--- Results ---")
    print(f"Retrieval hit-rate : {hit_rate:.0%}  (threshold {HIT_RATE_THRESHOLD:.0%})")
    print(f"Faithfulness       : {faithfulness:.0%}  (threshold {FAITHFULNESS_THRESHOLD:.0%})")

    ok = hit_rate >= HIT_RATE_THRESHOLD and faithfulness >= FAITHFULNESS_THRESHOLD
    print("\nPASS" if ok else "\nFAIL")
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
