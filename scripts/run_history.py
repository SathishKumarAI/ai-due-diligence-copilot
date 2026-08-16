"""Print the evaluation run history in ``data/runs.jsonl``.

    python scripts/run_history.py                 # every run, oldest first
    python scripts/run_history.py --kind eval     # one harness only
    python scripts/run_history.py --last 10       # the most recent N
    python scripts/run_history.py --config        # also show the config behind each run

The delta column is the point. A single hit-rate says nothing; a hit-rate that moved
from 90% to 70% between two commits says exactly where to look. Deltas are only shown
between runs of the same ``kind``, because comparing a Ragas faithfulness against an
LLM-judge faithfulness would be comparing two different judges.
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from scripts.run_log import RUNS_PATH, load_runs  # noqa: E402

# Higher is better for every metric currently recorded. Kept explicit rather than
# assumed: a latency or cost metric would need the opposite sign, and silently colouring
# a latency regression green is worse than not colouring it at all.
LOWER_IS_BETTER = {"latency_ms", "p95_ms", "duration_s"}


def _fmt(value: object) -> str:
    return f"{value:.3f}" if isinstance(value, float) else str(value)


def _delta(name: str, current: object, previous: object) -> str:
    if not isinstance(current, (int, float)) or not isinstance(previous, (int, float)):
        return ""
    diff = float(current) - float(previous)
    if abs(diff) < 1e-9:
        return "  (=)"
    better = diff < 0 if name in LOWER_IS_BETTER else diff > 0
    return f"  ({diff:+.3f} {'better' if better else 'worse'})"


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--kind", help="only runs from this harness (eval | ragas | simulate)")
    ap.add_argument("--last", type=int, help="only the most recent N runs")
    ap.add_argument("--config", action="store_true", help="show the config behind each run")
    ap.add_argument(
        "--path", type=Path, default=None, help="history file (default data/runs.jsonl)"
    )
    args = ap.parse_args()

    path = args.path or RUNS_PATH
    runs = load_runs(path)
    if args.kind:
        runs = [r for r in runs if r.get("kind") == args.kind]
    if not runs:
        # Exit 0: an empty history is the normal state before the first eval, not an
        # error. Say where it looked so "no runs" is not mistaken for "wrong file".
        print(f"No runs recorded in {path}")
        print("Run `python eval/run_eval.py` or `python eval/run_ragas.py` to record one.")
        return 0
    if args.last:
        runs = runs[-args.last :]

    previous_by_kind: dict[str, dict] = {}
    for run in runs:
        kind = run.get("kind", "?")
        sha = run.get("git_sha") or "unknown"
        dirty = run.get("git_dirty")
        # "dirty" is load-bearing: a metric from an uncommitted tree cannot be reproduced
        # from its SHA, so it is marked rather than quietly attributed to that commit.
        mark = "?" if dirty is None else ("+dirty" if dirty else "")
        print(f"\n{run.get('timestamp', '?')}  {kind:<9} {sha}{mark}")

        metrics = run.get("metrics", {})
        prev = previous_by_kind.get(kind, {}).get("metrics", {})
        for name, value in metrics.items():
            print(f"    {name:<20} {_fmt(value):>8}{_delta(name, value, prev.get(name))}")

        if args.config:
            config = run.get("config", {})
            print(f"    {'config':<20} " + "  ".join(f"{k}={v}" for k, v in config.items()))
        previous_by_kind[kind] = run

    print(f"\n{len(runs)} run(s) from {path}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
