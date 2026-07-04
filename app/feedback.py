"""Answer-feedback capture (feature F19).

Append-only JSONL via the standard library — no database, no new dependency. Each
👍/👎 from the UI becomes one line, the raw material for a usage-grounded eval set.
"""

from __future__ import annotations

import json
from datetime import UTC, datetime
from pathlib import Path


def record_feedback(
    path: Path,
    *,
    question: str,
    answer: str,
    rating: str,
    comment: str | None = None,
) -> dict:
    """Append one feedback row and return it. ``rating`` is ``up`` or ``down``."""
    row = {
        "ts": datetime.now(UTC).isoformat(),
        "question": question,
        "answer": answer,
        "rating": rating,
        "comment": comment or "",
    }
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8") as f:
        f.write(json.dumps(row, ensure_ascii=False) + "\n")
    return row


def feedback_summary(path: Path) -> dict:
    """Counts of up/down feedback recorded so far (0s if none yet)."""
    up = down = 0
    if path.exists():
        with path.open(encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if not line:
                    continue
                try:
                    rating = json.loads(line).get("rating")
                except json.JSONDecodeError:
                    continue
                if rating == "up":
                    up += 1
                elif rating == "down":
                    down += 1
    return {"up": up, "down": down, "total": up + down}
