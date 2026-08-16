#!/usr/bin/env bash
# Regenerate the dependency lockfiles from requirements*.txt.
#
# Run this whenever a range in requirements.txt or requirements-dev.txt changes, and
# commit the result. The ranges are the intent; the locks are what actually gets
# installed. Everything that drifted between July and August 2026 — a ruff formatter
# that reformatted 14 files, a numpy whose stubs mypy could not parse, a langchain
# whose provider kwargs moved — drifted because there was no lock.
#
#   ./scripts/lock.sh
set -euo pipefail
cd "$(dirname "$0")/.."

command -v uv >/dev/null || { echo "uv not found: https://docs.astral.sh/uv/" >&2; exit 1; }

uv pip compile requirements.txt     -c constraints.txt -o requirements.lock
uv pip compile requirements-dev.txt -c constraints.txt -o requirements-dev.lock

echo
echo "Locked. torch pinned to: $(grep '^torch==' requirements.lock)"
echo "Check that version exists at https://download.pytorch.org/whl/cu128/torch/"
echo "before shipping — see constraints.txt for why that matters."
