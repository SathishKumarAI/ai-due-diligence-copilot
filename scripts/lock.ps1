# Regenerate the dependency lockfiles from requirements*.txt. See scripts/lock.sh for
# the rationale; this is the Windows equivalent.
#
#   .\scripts\lock.ps1
$ErrorActionPreference = "Stop"
Set-Location (Join-Path $PSScriptRoot "..")

if (-not (Get-Command uv -ErrorAction SilentlyContinue)) {
  throw "uv not found: https://docs.astral.sh/uv/"
}

# --universal: see scripts/lock.sh. Locking without it on Windows drops triton, uvloop
# and the nvidia-* wheels, which makes the CI freshness check unsatisfiable and leaves
# the Linux image's torch dependencies unpinned.
uv pip compile requirements.txt     -c constraints.txt --universal -o requirements.lock
uv pip compile requirements-dev.txt -c constraints.txt --universal -o requirements-dev.lock

$pin = (Select-String -Path requirements.lock -Pattern '^torch==').Line
Write-Host ""
Write-Host "Locked. torch pinned to: $pin"
Write-Host "Check that version exists at https://download.pytorch.org/whl/cu128/torch/"
Write-Host "before shipping - see constraints.txt for why that matters."
