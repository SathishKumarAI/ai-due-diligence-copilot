"""Generate an evaluation testset from the corpus itself (Ragas).

The hand-written set in ``eval/qa_dataset.jsonl`` is ten questions, and every one of them
is a single-fact lookup. That shape hides whole classes of failure: a change that
improved fact lookup while destroying synthesis would score as an improvement. Ragas can
build questions *from the documents*, including multi-hop ones no one thought to write.

    python scripts/generate_testset.py                # 10 questions -> eval/qa_generated.jsonl
    python scripts/generate_testset.py --size 25
    python scripts/generate_testset.py --out eval/other.jsonl

**Output is written to a separate file and stays separate.** Generated questions are
useful in bulk and unreliable individually - a local 8B model writing its own ground
truth produces some questions the corpus cannot actually answer, and some whose
"reference" answer is wrong. Merging them into qa_dataset.jsonl would quietly corrupt the
one dataset that is trusted. Read what comes out before you rely on it; this script
prints every question for exactly that reason.

Dev-only: ragas lives in requirements-dev.txt and nothing in app/ imports it.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app.config import settings  # noqa: E402
from app.ingest import load_documents  # noqa: E402

DEFAULT_OUT = Path(__file__).resolve().parent.parent / "eval" / "qa_generated.jsonl"


def build_embeddings():  # noqa: ANN201 - ragas type is internal
    """Wrap the project's own embedding model for Ragas.

    ``LangchainEmbeddingsWrapper`` already adapts any LangChain embeddings object to the
    interface Ragas wants, so there is nothing to write here. Using the *same* model the
    index was built with matters: the knowledge graph Ragas builds to find multi-hop
    relationships is clustered in the same vector space retrieval will later search, so
    the questions it invents are questions this pipeline could plausibly be asked.

    Ragas deprecates this wrapper in favour of its own ``HuggingFaceEmbeddings``, and the
    deprecation is not being followed on purpose: that class constructs its own model from
    a name, which would silently drop this project's device selection (app/device.py) and
    embedding cache, and could load a *different* model from the one the index was built
    with. Losing that guarantee to silence a warning is a bad trade. Revisit if the
    wrapper is actually removed.
    """
    from ragas.embeddings import LangchainEmbeddingsWrapper

    from app.providers import get_embeddings

    return LangchainEmbeddingsWrapper(get_embeddings(settings))


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--size", type=int, default=10, help="how many questions to generate")
    ap.add_argument("--out", type=Path, default=DEFAULT_OUT, help="output JSONL path")
    args = ap.parse_args()

    from ragas.testset import TestsetGenerator

    from eval.run_ragas import build_judge  # the same local judge, not a second config

    docs = load_documents(settings.data_dir, settings)
    if not docs:
        print(f"No documents found under {settings.data_dir}. Run the generator or ingest first.")
        return 1

    print(f"provider={settings.provider} model={settings.ollama_llm_model}")
    print(f"Building a knowledge graph over {len(docs)} document(s), then {args.size} questions…")
    print("This is slow on a local 8B model - it extracts entities and relationships first.")

    generator = TestsetGenerator(llm=build_judge(), embedding_model=build_embeddings())
    testset = generator.generate_with_langchain_docs(docs, testset_size=args.size)

    rows = []
    for sample in testset.to_list():
        # Ragas' column names differ from this repo's dataset schema; translate rather
        # than teach run_eval.py a second format.
        contexts = sample.get("reference_contexts") or []
        rows.append(
            {
                "question": sample.get("user_input", ""),
                "expected_answer": sample.get("reference", ""),
                # No expected_source: Ragas returns the context text, not the file it came
                # from. Writing a guess here would silently corrupt the retrieval
                # hit-rate, which is computed by comparing this field against the sources
                # actually retrieved.
                "expected_source": None,
                "generated": True,
                "reference_contexts": contexts,
            }
        )

    args.out.parent.mkdir(parents=True, exist_ok=True)
    with args.out.open("w", encoding="utf-8", newline="\n") as fh:
        for row in rows:
            fh.write(json.dumps(row, ensure_ascii=False) + "\n")

    print(f"\nWrote {len(rows)} questions to {args.out}\n")
    for i, row in enumerate(rows, 1):
        print(f"  {i:>2}. {row['question']}")
    print(
        "\nRead these before trusting them. Generated ground truth is not verified ground\n"
        "truth, and this file is deliberately NOT merged into eval/qa_dataset.jsonl."
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
