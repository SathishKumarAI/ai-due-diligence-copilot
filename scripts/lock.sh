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

# --universal is load-bearing, not a nicety. Without it uv resolves for the platform it
# happens to be running on: locking on Windows omits triton, uvloop and every nvidia-*
# wheel, because they do not exist there. Two consequences, both real:
#
#   - CI recompiles on Linux to check the lock is fresh, gets a different answer every
#     time, and reports a stale lock that no amount of re-locking can fix.
#   - The Docker image is Linux and installs requirements.lock. A Windows-authored lock
#     silently leaves torch's Linux dependencies unpinned, so the image resolves them
#     itself and the lock stops describing what ships.
#
# --universal emits one resolution covering every platform, with environment markers.
uv pip compile requirements.txt     -c constraints.txt --universal -o requirements.lock
uv pip compile requirements-dev.txt -c constraints.txt --universal -o requirements-dev.lock

echo
echo "Locked. torch pinned to: $(grep '^torch==' requirements.lock)"
echo "Check that version exists at https://download.pytorch.org/whl/cu128/torch/"
echo "before shipping — see constraints.txt for why that matters."
