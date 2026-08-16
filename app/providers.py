"""Model factory — returns LLM and embeddings for the configured provider.

Keeping this behind one module means the rest of the app never imports a
provider-specific class directly; swapping backends is a single env var.
"""

from __future__ import annotations

from typing import Any

from langchain_core.embeddings import Embeddings
from langchain_core.language_models.chat_models import BaseChatModel
from pydantic import SecretStr

from app.config import Settings


def _api_key_kwarg(key: str | None) -> dict[str, Any]:
    """Pass ``api_key`` only when we actually have one.

    Both ChatAnthropic and VoyageAIEmbeddings declare ``api_key`` as an optional
    *non-nullable* ``SecretStr``: omitting it falls back to the ANTHROPIC_API_KEY /
    VOYAGE_API_KEY environment variable, but passing an explicit ``None`` fails
    validation outright. Sending ``settings.x_api_key or None`` therefore crashed
    exactly the env-var path DEPLOYMENT.md tells people to use.
    """
    return {"api_key": SecretStr(key)} if key else {}


def _ensure_cloud_allowed(settings: Settings) -> None:
    """Refuse the cloud provider when running fully local (LOCAL_ONLY)."""
    if settings.local_only:
        raise RuntimeError(
            "LOCAL_ONLY is enabled: the Claude/Voyage cloud provider is disabled. "
            "Set LOCAL_ONLY=false to use PROVIDER=claude."
        )


def get_embeddings(settings: Settings) -> Embeddings:
    if settings.provider == "ollama":
        from langchain_huggingface import HuggingFaceEmbeddings

        from app.device import resolve_device

        # Local sentence-transformers model; downloads once, then runs offline.
        # device: "auto" picks cuda -> mps -> cpu (see app/device.py / EMBED_DEVICE).
        return HuggingFaceEmbeddings(
            model_name=settings.hf_embed_model,
            model_kwargs={"device": resolve_device(settings.embed_device)},
        )

    if settings.provider == "claude":
        _ensure_cloud_allowed(settings)
        from langchain_voyageai import VoyageAIEmbeddings

        return VoyageAIEmbeddings(
            model=settings.voyage_model,
            **_api_key_kwarg(settings.voyage_api_key),
        )

    raise ValueError(f"Unknown provider: {settings.provider!r}")


def get_llm(settings: Settings) -> BaseChatModel:
    if settings.provider == "ollama":
        from langchain_ollama import ChatOllama

        return ChatOllama(
            model=settings.ollama_llm_model,
            base_url=settings.ollama_base_url,
            temperature=0,
            num_predict=settings.max_tokens,
        )

    if settings.provider == "claude":
        _ensure_cloud_allowed(settings)
        from langchain_anthropic import ChatAnthropic

        # The ignore below is needed because ChatAnthropic declares `model` and
        # `max_tokens` under the aliases `model_name` / `max_tokens_to_sample`, which is
        # all mypy's pydantic plugin sees. populate_by_name=True makes these names correct
        # at runtime, and they are the spelling langchain documents.
        return ChatAnthropic(  # type: ignore[call-arg]
            model=settings.anthropic_model,
            max_tokens=settings.max_tokens,
            **_api_key_kwarg(settings.anthropic_api_key),
        )

    raise ValueError(f"Unknown provider: {settings.provider!r}")
