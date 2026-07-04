"""Engine parity test: the shared RAG engine must not drift from the manifest.

The three sibling repos share one engine (see scripts/sync_engine.py). Each repo carries
an ``ENGINE_MANIFEST.sha256`` of the canonical engine-file hashes. If someone edits an
engine file in one repo without re-syncing, this test fails — the fix is to make the
change in the reference repo and run ``python scripts/sync_engine.py --to <siblings>``,
which recopies the files and rewrites the manifest everywhere.

Per-project files (app/config.py, app/prompts.py, data/, eval/) are intentionally NOT
in the manifest — they are expected to differ across repos.
"""

from __future__ import annotations

import hashlib
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
MANIFEST = REPO_ROOT / "ENGINE_MANIFEST.sha256"


def test_engine_files_match_manifest():
    assert MANIFEST.exists(), "Missing ENGINE_MANIFEST.sha256 — run scripts/sync_engine.py --manifest-only"
    for line in MANIFEST.read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue
        expected, rel = line.split(maxsplit=1)
        rel = rel.strip()
        path = REPO_ROOT / rel
        assert path.exists(), f"Engine file listed in manifest is missing: {rel}"
        actual = hashlib.sha256(path.read_bytes()).hexdigest()
        assert actual == expected, (
            f"Engine drift in {rel}. Edit it in the reference repo and re-run "
            f"scripts/sync_engine.py to re-sync all siblings."
        )
