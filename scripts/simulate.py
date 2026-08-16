#!/usr/bin/env python3
"""Replay a question across retrieval configurations and diff what the LLM saw (F24).

The pipeline inspector (F23) explains one answer under one configuration. It cannot
answer the question you actually have when tuning: *would a different retrieval setup
have put better evidence in front of the model?* Comparing that by hand means editing
.env, restarting, re-asking, and holding two traces in your head.

This runs the same question through several configurations against one already-built
index and prints what changed — which chunks were retrieved, how much context the model
received, and how well the resulting answer was grounded in it (F24).

    python scripts/simulate.py "What is the ARR and its growth?"
    python scripts/simulate.py --dataset          # every question in eval/qa_dataset.jsonl
    python scripts/simulate.py "..." --show-prompt  # print the exact prompt per config
    python scripts/simulate.py "..." --rerank       # include cross-encoder configs

Reranking is opt-in because the cross-encoder downloads a model on first use, which
would make an otherwise offline comparison reach for the network without being asked.
"""

from __future__ import annotations

import argparse
import json
import sys
from dataclasses import dataclass
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app.cache import wrap_embeddings  # noqa: E402
from app.config import settings  # noqa: E402
from app.ingest import load_index  # noqa: E402
from app.providers import get_embeddings, get_llm  # noqa: E402
from app.rag import RagEngine  # noqa: E402
from app.rerank import build_reranker  # noqa: E402
from app.retrieval import build_retriever  # noqa: E402
from scripts.run_log import record_run  # noqa: E402


@dataclass
class Config:
    label: str
    retrieval_mode: str
    rerank_enabled: bool
    top_k: int


def configs(base_top_k: int, with_rerank: bool) -> list[Config]:
    out = [
        Config("dense", "dense", False, base_top_k),
        Config("hybrid", "hybrid", False, base_top_k),
        Config(f"hybrid k={base_top_k * 2}", "hybrid", False, base_top_k * 2),
    ]
    if with_rerank:
        out += [
            Config("dense+rerank", "dense", True, base_top_k),
            Config("hybrid+rerank", "hybrid", True, base_top_k),
        ]
    return out


def build(store, llm, cfg: Config) -> RagEngine:  # noqa: ANN001
    """An engine for one configuration, built through the same seams the API uses."""
    tuned = settings.model_copy(
        update={
            "retrieval_mode": cfg.retrieval_mode,
            "rerank_enabled": cfg.rerank_enabled,
            "top_k": cfg.top_k,
        }
    )
    return RagEngine(
        store,
        llm,
        top_k=tuned.top_k,
        provider=tuned.provider,
        retriever=build_retriever(store, tuned),
        reranker=build_reranker(tuned),
        fetch_k=tuned.retrieve_fetch_k,
        history_max_turns=tuned.history_max_turns,
        # Omitted when the source-diversity cap was added, which silently made every
        # config here uncapped — so the tool for deciding what ships was comparing a
        # retrieval stack that does not ship.
        max_chunks_per_source=tuned.max_chunks_per_source,
    )


def run_question(
    store, llm, question: str, cfgs: list[Config], show_prompt: bool
) -> dict[str, float]:  # noqa: ANN001
    """Print the per-config comparison, and return each config's grounding score.

    The scores are returned rather than only printed so main() can record the run: a
    comparison whose result only ever reached the terminal could not be compared against
    the next one, which is the whole point of running it.
    """
    print(f"\n{'=' * 78}\nQ: {question}\n{'=' * 78}")
    header = f"{'config':<16} {'sources retrieved':<44} {'ctx':>6} {'grounding':>22}"
    print(header)
    print("-" * len(header))

    scores: dict[str, float] = {}
    for cfg in cfgs:
        engine = build(store, llm, cfg)
        answer, trace = engine.answer_with_trace(question, verify=True)
        sources = ", ".join(c.source for c in trace.retrieved) or "(none)"
        g = answer.grounding
        verdict = (
            f"{g.verdict} {g.score:.2f} (g{g.grounded}/w{g.weak}/u{g.unsupported})" if g else "-"
        )
        print(f"{cfg.label:<16} {sources[:44]:<44} {trace.context_char_len:>6} {verdict:>22}")
        if g:
            scores[cfg.label] = g.score

        if show_prompt:
            print(f"\n--- prompt under {cfg.label} ---\n{trace.user_prompt}\n")

        # Unsupported claims are the reason to run this at all: surface them inline.
        for claim in g.claims if g else []:
            if claim.status == "unsupported":
                figures = (
                    f" figures={claim.unsupported_figures}" if claim.unsupported_figures else ""
                )
                print(f"{'':<16} !! unsupported: {claim.text[:60]}{figures}")

    return scores


def main() -> int:
    ap = argparse.ArgumentParser(description="Compare retrieval configurations on one index.")
    ap.add_argument("question", nargs="?", help="Question to replay")
    ap.add_argument("--dataset", action="store_true", help="Replay every eval question")
    ap.add_argument("--rerank", action="store_true", help="Include cross-encoder configs")
    ap.add_argument("--show-prompt", action="store_true", help="Print the prompt per config")
    args = ap.parse_args()

    if not args.question and not args.dataset:
        ap.error("give a question, or --dataset")

    questions: list[str] = []
    if args.question:
        questions.append(args.question)
    if args.dataset:
        dataset = Path(__file__).resolve().parent.parent / "eval" / "qa_dataset.jsonl"
        questions += [
            json.loads(line)["question"]
            for line in dataset.read_text(encoding="utf-8").splitlines()
            if line.strip()
        ]

    embeddings = wrap_embeddings(get_embeddings(settings), settings)
    store = load_index(settings, embeddings)
    llm = get_llm(settings)
    cfgs = configs(settings.top_k, args.rerank)

    print(f"provider={settings.provider} model={settings.ollama_llm_model}")
    print(f"comparing {len(cfgs)} configs over {len(questions)} question(s)")
    per_config: dict[str, list[float]] = {}
    for question in questions:
        for label, score in run_question(store, llm, question, cfgs, args.show_prompt).items():
            per_config.setdefault(label, []).append(score)

    # Metric names carry the config label because that is exactly what varies here — the
    # run's global config snapshot describes the index, not the configs being compared.
    record_run(
        "simulate",
        {f"grounding[{label}]": round(sum(v) / len(v), 3) for label, v in per_config.items() if v},
        extra={"questions": len(questions), "configs": [c.label for c in cfgs]},
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
