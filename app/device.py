"""Compute-device resolution for the local (Ollama/HuggingFace) provider path.

Embeddings and the F17 cross-encoder run through sentence-transformers / torch, which
place a model on a specific device. This module turns a settings string
(``"auto" | "cpu" | "cuda" | "mps"``) into the concrete device torch should use.

``auto`` is the default: it prefers an NVIDIA GPU (``cuda``), then Apple Metal (``mps``),
then falls back to ``cpu``. The torch import is lazy and guarded so the engine still
imports (and CPU-only tests still run) when torch or a GPU is absent.
"""

from __future__ import annotations

_EXPLICIT = {"cpu", "cuda", "mps"}


def resolve_device(preference: str = "auto") -> str:
    """Return the torch device string for the given preference.

    Explicit ``cpu``/``cuda``/``mps`` are honored verbatim (no probing) so an operator
    can force a device. ``auto`` (or anything unrecognized) probes for the best available.
    """
    pref = (preference or "auto").strip().lower()
    if pref in _EXPLICIT:
        return pref

    try:
        import torch

        if torch.cuda.is_available():
            return "cuda"
        mps = getattr(torch.backends, "mps", None)
        if mps is not None and mps.is_available():
            return "mps"
    except Exception:
        # torch missing or a probe blew up — CPU is always safe.
        pass
    return "cpu"
