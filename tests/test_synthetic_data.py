"""Pins ``data/`` to the generator that claims to produce it.

These exist because the two silently diverged. ``data/`` was hand-edited over time with
content the generator's templates never had, so running the documented entry point
``python scripts/generate_synthetic_data.py`` would have *deleted* the pre-money
valuation, board composition, pro-rata rights, cost of revenue, total debt and two whole
risk sections — several of which ``eval/qa_dataset.jsonl`` asks about. Nothing failed;
the corpus would just have quietly lost facts and the eval set would have started
failing as though retrieval had regressed.
"""

from __future__ import annotations

import importlib.util
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
_spec = importlib.util.spec_from_file_location(
    "generate_synthetic_data", ROOT / "scripts" / "generate_synthetic_data.py"
)
gen = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(gen)  # type: ignore[union-attr]


def test_generator_reproduces_the_committed_corpus():
    """Every file in data/ is byte-identical to the template that claims to generate it."""
    assert gen.check() == [], (
        "data/ has drifted from scripts/generate_synthetic_data.py. Reconcile them — "
        "and decide which is right, because the generator overwrites data/."
    )


def test_generated_bytes_are_platform_independent(tmp_path, monkeypatch):
    """Writing on Windows must produce the same bytes as writing on Linux.

    The templates are LF. Python's default text mode translates "\\n" to CRLF on Windows,
    which would change every byte offset in the corpus, rechunk the whole index, and make
    the committed data/ un-regenerable on half the machines that run this.
    """
    monkeypatch.setattr(gen, "DATA_DIR", tmp_path)
    assert gen.main([]) == 0

    for name in gen.CORPUS:
        written = (tmp_path / name).read_bytes()
        assert b"\r\n" not in written, f"{name} was written with CRLF line endings"
        assert written == (ROOT / "data" / name).read_bytes()


def test_every_eval_question_points_at_a_real_corpus_file():
    """A ground-truth ``expected_source`` naming a file that does not exist scores 0 forever.

    The retrieval hit-rate is computed by comparing retrieved sources against this field,
    so a typo or a renamed document reads exactly like a retrieval failure.
    """
    dataset = ROOT / "eval" / "qa_dataset.jsonl"
    rows = [json.loads(line) for line in dataset.read_text(encoding="utf-8").splitlines() if line]
    assert rows, "eval dataset is empty"

    missing = sorted(
        {
            row["expected_source"]
            for row in rows
            if row.get("expected_source") and not (ROOT / "data" / row["expected_source"]).exists()
        }
    )
    assert not missing, f"eval questions cite corpus files that do not exist: {missing}"
