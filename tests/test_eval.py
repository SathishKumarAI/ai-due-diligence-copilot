"""Tests for the F10 eval harness (``eval/run_eval.py``).

Loaded by path because ``eval/`` is not a package (the harness is a script, and its
documented invocation is ``python eval/run_eval.py``).
"""

from __future__ import annotations

import importlib.util
from pathlib import Path

_SPEC = importlib.util.spec_from_file_location(
    "run_eval", Path(__file__).resolve().parent.parent / "eval" / "run_eval.py"
)
assert _SPEC and _SPEC.loader
run_eval = importlib.util.module_from_spec(_SPEC)
_SPEC.loader.exec_module(run_eval)


def test_judge_rejects_negated_groundedness():
    # The failure this catches: `"GROUNDED" in verdict.upper()` also matches
    # "NOT GROUNDED", so a judge rejecting an answer scored it as a pass and
    # faithfulness could only ever be over-reported.
    assert run_eval.is_grounded("GROUNDED")
    assert run_eval.is_grounded("  grounded  ")
    assert not run_eval.is_grounded("UNSUPPORTED")
    assert not run_eval.is_grounded("NOT GROUNDED")
    assert not run_eval.is_grounded("The answer is not grounded in the context.")


def test_judge_fails_closed_on_a_non_answer():
    # A judge that waffles must not be counted as a pass.
    assert not run_eval.is_grounded("")
    assert not run_eval.is_grounded("I cannot determine this.")


def test_eval_thresholds_are_gates_not_decoration():
    assert run_eval.HIT_RATE_THRESHOLD > 0
    assert run_eval.FAITHFULNESS_THRESHOLD > 0
