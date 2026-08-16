"""Offline tests for the evaluation run history (scripts/run_log.py)."""

from __future__ import annotations

import importlib.util
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
_spec = importlib.util.spec_from_file_location("run_log", ROOT / "scripts" / "run_log.py")
run_log = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(run_log)  # type: ignore[union-attr]


def test_records_append_rather_than_replace(tmp_path):
    """History is only useful if a second run cannot erase the first."""
    path = tmp_path / "runs.jsonl"
    run_log.record_run("eval", {"hit_rate": 0.9}, path=path)
    run_log.record_run("eval", {"hit_rate": 0.7}, path=path)

    rows = run_log.load_runs(path)
    assert [r["metrics"]["hit_rate"] for r in rows] == [0.9, 0.7]


def test_each_row_carries_the_config_that_produced_it(tmp_path):
    """A metric without its config is not comparable to the next one.

    chunk_size has already changed once in this repo, which silently redefined every
    earlier hit-rate.
    """
    path = tmp_path / "runs.jsonl"
    run_log.record_run("eval", {"hit_rate": 1.0}, path=path)

    config = run_log.load_runs(path)[0]["config"]
    for key in ("chunk_size", "top_k", "retrieval_mode", "model", "max_chunks_per_source"):
        assert key in config, f"config snapshot is missing {key}"


def test_history_is_written_as_lf_regardless_of_platform(tmp_path):
    """A Windows run must not append CRLF to a file a Linux run appends LF to."""
    path = tmp_path / "runs.jsonl"
    run_log.record_run("eval", {"hit_rate": 1.0}, path=path)
    assert b"\r\n" not in path.read_bytes()


def test_a_corrupt_line_does_not_make_the_history_unreadable(tmp_path):
    """An interrupted run leaves a half-written line; the rest must still load."""
    path = tmp_path / "runs.jsonl"
    run_log.record_run("eval", {"hit_rate": 0.9}, path=path)
    with path.open("a", encoding="utf-8", newline="\n") as fh:
        fh.write('{"timestamp": "truncated mid-writ\n')
    run_log.record_run("eval", {"hit_rate": 0.8}, path=path)

    rows = run_log.load_runs(path)
    assert [r["metrics"]["hit_rate"] for r in rows] == [0.9, 0.8]


def test_recording_never_raises_even_when_the_path_is_unwritable(tmp_path):
    """Recording history is a side effect; it must not fail a run that already succeeded."""
    blocker = tmp_path / "not_a_dir"
    blocker.write_text("i am a file", encoding="utf-8")

    # parent is a regular file, so mkdir/open must fail
    run_log.record_run("eval", {"hit_rate": 1.0}, path=blocker / "runs.jsonl")


def test_git_dirty_is_none_when_git_is_unavailable(tmp_path, monkeypatch):
    """Without git, dirty must be None — never False, which would read as 'clean'."""
    import subprocess

    def boom(*args, **kwargs):
        raise OSError("git not found")

    monkeypatch.setattr(subprocess, "run", boom)

    path = tmp_path / "runs.jsonl"
    run_log.record_run("eval", {"hit_rate": 1.0}, path=path)
    row = json.loads(path.read_text(encoding="utf-8").strip())
    assert row["git_sha"] is None
    assert row["git_dirty"] is None
