#!/usr/bin/env python3
"""Replicate the shared RAG engine across the sibling repos + refresh the parity manifest.

The three RAG apps are standalone repos that share ONE engine and differ only in
per-project files (prompt, config defaults, corpus, eval). This script copies the
shared engine files from THIS repo (the reference) to the sibling repos, then writes
``ENGINE_MANIFEST.sha256`` into every repo so ``tests/test_parity.py`` can detect drift.

Shared (copied):   the engine modules below.
Per-project (never touched): app/__init__.py, app/config.py, app/prompts.py, data/, eval/.

Usage (run from the reference repo root):
    python scripts/sync_engine.py --check                       # report drift, copy nothing
    python scripts/sync_engine.py --to ../healthcare-knowledge-navigator ../engineering-intelligence-hub
    python scripts/sync_engine.py --manifest-only               # just (re)write the local manifest
"""

from __future__ import annotations

import argparse
import hashlib
import shutil
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent

# The engine. Identical across all three repos. Per-project files are NOT listed here.
SHARED_ENGINE_FILES: list[str] = [
    "app/cache.py",
    "app/cleaning.py",
    "app/device.py",
    "app/feedback.py",
    "app/ingest.py",
    "app/main.py",
    "app/observability.py",
    "app/ocr.py",
    "app/providers.py",
    "app/rag.py",
    "app/rerank.py",
    "app/retrieval.py",
    "app/schemas.py",
    "app/security.py",
    "app/trace.py",
]

MANIFEST_NAME = "ENGINE_MANIFEST.sha256"


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def write_manifest(repo: Path) -> None:
    lines = [f"{sha256(repo / rel)}  {rel}" for rel in SHARED_ENGINE_FILES]
    (repo / MANIFEST_NAME).write_text("\n".join(lines) + "\n", encoding="utf-8")


def copy_to(target: Path) -> list[str]:
    changed: list[str] = []
    for rel in SHARED_ENGINE_FILES:
        src, dst = REPO_ROOT / rel, target / rel
        dst.parent.mkdir(parents=True, exist_ok=True)
        if not dst.exists() or sha256(src) != sha256(dst):
            shutil.copy2(src, dst)
            changed.append(rel)
    write_manifest(target)
    return changed


def check(repo: Path) -> list[str]:
    """Return engine files whose hash differs from the reference repo."""
    return [rel for rel in SHARED_ENGINE_FILES if sha256(repo / rel) != sha256(REPO_ROOT / rel)]


def main() -> None:
    ap = argparse.ArgumentParser(description="Sync the shared RAG engine across repos.")
    ap.add_argument("--to", nargs="*", type=Path, default=[], help="sibling repo roots")
    ap.add_argument("--check", action="store_true", help="report drift vs reference, copy nothing")
    ap.add_argument("--manifest-only", action="store_true", help="rewrite this repo's manifest")
    args = ap.parse_args()

    if args.manifest_only:
        write_manifest(REPO_ROOT)
        print(f"Wrote {MANIFEST_NAME} for {REPO_ROOT.name}")
        return

    # The reference repo's manifest must always reflect its own engine.
    write_manifest(REPO_ROOT)

    for target in args.to:
        target = target.resolve()
        if args.check:
            drift = check(target)
            print(f"{target.name}: {'in sync' if not drift else 'DRIFT: ' + ', '.join(drift)}")
        else:
            changed = copy_to(target)
            print(f"{target.name}: synced ({len(changed)} file(s) updated)")
            for rel in changed:
                print(f"    {rel}")


if __name__ == "__main__":
    main()
