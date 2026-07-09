"""Offline tests for compute-device resolution (app/device.py).

Pure string logic — no torch/GPU required. Explicit devices pass through; ``auto``
resolves to one of the known device strings.
"""

from __future__ import annotations

import pytest

from app.device import resolve_device


@pytest.mark.parametrize("value", ["cpu", "cuda", "mps"])
def test_explicit_device_passes_through(value: str) -> None:
    assert resolve_device(value) == value


@pytest.mark.parametrize("value", ["CPU", "Cuda", "  MPS  "])
def test_explicit_device_is_normalized(value: str) -> None:
    assert resolve_device(value) == value.strip().lower()


def test_auto_resolves_to_a_known_device() -> None:
    # cuda -> mps -> cpu depending on the host; always one of these, never raises.
    assert resolve_device("auto") in {"cpu", "cuda", "mps"}


def test_blank_or_unknown_falls_back_like_auto() -> None:
    assert resolve_device("") in {"cpu", "cuda", "mps"}
    assert resolve_device("gpu-please") in {"cpu", "cuda", "mps"}
