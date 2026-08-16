"""Append-only history of evaluation runs (``data/runs.jsonl``).

Every quality number this project produces is a single point in time. `run_eval.py`
prints a hit-rate, `run_ragas.py` prints three scores, `simulate.py` compares configs —
and then the terminal scrolls and the number is gone. Nothing could answer the one
question that actually matters when a change lands: **did this get better or worse?**

That gap is what a tracing backend was wanted for, and it does not need one. Phoenix and
Langfuse were both evaluated and rejected (ADR 0003, ADR 0004); the honest requirement is
not distributed tracing — F23 already traces any single answer and F24 verifies it — but
that *nothing accumulates across runs*. One JSON line per run closes it with no
dependency and no service.

Deliberately append-only and deliberately dumb:

- **A line is never rewritten.** Comparing runs is only meaningful if history is not
  edited after the fact, and an appender that cannot rewrite cannot silently launder a
  bad result.
- **The config is recorded next to the metrics.** A hit-rate is meaningless without the
  chunk size, retrieval mode and top_k that produced it — this repo has already changed
  chunk_size once, and every earlier measurement silently means something different.
- **The git SHA and dirty flag are recorded.** A metric from an uncommitted tree is not
  reproducible, and pretending otherwise is how a number outlives the code that made it.
"""

from __future__ import annotations

import json
import subprocess
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

PROJECT_ROOT = Path(__file__).resolve().parent.parent
RUNS_PATH = PROJECT_ROOT / "data" / "runs.jsonl"


def git_revision() -> dict[str, Any]:
    """Short SHA and whether the tree was dirty, or unknowns when git is unavailable.

    Never raises. A history line is worth writing even from a tarball with no .git.
    """

    def _git(*args: str) -> str | None:
        try:
            out = subprocess.run(
                ["git", *args],
                cwd=PROJECT_ROOT,
                capture_output=True,
                text=True,
                timeout=10,
                check=True,
            )
        except (OSError, subprocess.SubprocessError):
            return None
        return out.stdout.strip()

    sha = _git("rev-parse", "--short", "HEAD")
    status = _git("status", "--porcelain")
    return {
        "git_sha": sha,
        # None, not False, when git could not be reached: "the tree was clean" and "we
        # could not tell" are different claims and only one of them is reassuring.
        "git_dirty": None if status is None else bool(status),
    }


def config_snapshot() -> dict[str, Any]:
    """The settings that change what a metric means."""
    from app.config import settings

    return {
        "provider": settings.provider,
        "model": (
            settings.anthropic_model if settings.provider == "claude" else settings.ollama_llm_model
        ),
        "embed_model": settings.hf_embed_model,
        "retrieval_mode": settings.retrieval_mode,
        "chunk_size": settings.chunk_size,
        "chunk_overlap": settings.chunk_overlap,
        "top_k": settings.top_k,
        "fetch_k": settings.retrieve_fetch_k,
        "rerank_enabled": settings.rerank_enabled,
        "max_chunks_per_source": settings.max_chunks_per_source,
    }


def record_run(
    kind: str,
    metrics: dict[str, Any],
    extra: dict[str, Any] | None = None,
    path: Path | None = None,
) -> Path:
    """Append one run to the history and return the file it was written to.

    ``kind`` names the harness ("eval", "ragas", "simulate") so runs from different
    harnesses can be read apart. Never raises: recording history must not be able to
    fail a run whose actual work already succeeded.
    """
    target = path or RUNS_PATH
    row = {
        "timestamp": datetime.now(UTC).isoformat(timespec="seconds"),
        "kind": kind,
        **git_revision(),
        "config": config_snapshot(),
        "metrics": metrics,
    }
    if extra:
        row["extra"] = extra
    try:
        target.parent.mkdir(parents=True, exist_ok=True)
        # newline="\n" so a Windows run does not write CRLF into a file a Linux run
        # appends LF to, leaving the history mixed and awkward to read.
        with target.open("a", encoding="utf-8", newline="\n") as fh:
            fh.write(json.dumps(row, ensure_ascii=False) + "\n")
    except OSError as exc:  # noqa: BLE001 - history is a side effect, never the point
        print(f"warning: could not record run history: {exc}")
    return target


def load_runs(path: Path | None = None) -> list[dict[str, Any]]:
    """Every recorded run, oldest first. Malformed lines are skipped, not fatal."""
    target = path or RUNS_PATH
    if not target.exists():
        return []
    rows = []
    for line in target.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line:
            continue
        try:
            rows.append(json.loads(line))
        except json.JSONDecodeError:
            # A half-written line from an interrupted run must not make the whole
            # history unreadable.
            continue
    return rows
