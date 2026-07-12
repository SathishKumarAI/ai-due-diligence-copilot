"""Model factory — returns LLM and embeddings for the configured provider.

Keeping this behind one module means the rest of the app never imports a
provider-specific class directly; swapping backends is a single env var.
"""
from __future__ import annotations

from langchain_core.embeddings import Embeddings
from langchain_core.language_models.chat_models import BaseChatModel

from app.config import Settings


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
            api_key=settings.voyage_api_key or None,
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

        return ChatAnthropic(
            model=settings.anthropic_model,
            api_key=settings.anthropic_api_key or None,
            max_tokens=settings.max_tokens,
        )

    raise ValueError(f"Unknown provider: {settings.provider!r}")
