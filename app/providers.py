"""Model factory — returns LLM and embeddings for the configured provider.

Keeping this behind one module means the rest of the app never imports a
provider-specific class directly; swapping backends is a single env var.

The two halves are chosen independently: get_llm follows LLM_PROVIDER and
get_embeddings follows EMBED_PROVIDER, each falling back to PROVIDER. Mixing is
the point — a local generator against cloud embeddings, or the reverse.
"""

from __future__ import annotations

from typing import Any
from urllib.parse import urlsplit

from langchain_core.embeddings import Embeddings
from langchain_core.language_models.chat_models import BaseChatModel
from pydantic import SecretStr

from app.config import LOCAL_HOSTS, ProviderName, Settings


def _api_key_kwarg(key: str | None) -> dict[str, Any]:
    """Pass ``api_key`` only when we actually have one.

    Both ChatAnthropic and VoyageAIEmbeddings declare ``api_key`` as an optional
    *non-nullable* ``SecretStr``: omitting it falls back to the ANTHROPIC_API_KEY /
    VOYAGE_API_KEY environment variable, but passing an explicit ``None`` fails
    validation outright. Sending ``settings.x_api_key or None`` therefore crashed
    exactly the env-var path DEPLOYMENT.md tells people to use.
    """
    return {"api_key": SecretStr(key)} if key else {}


def _is_cloud(provider: ProviderName, settings: Settings) -> bool:
    """Does this provider send text off the machine?

    "openai" is the one that cannot be answered by name. The OpenAI wire format is
    what vLLM, TGI, LM Studio and Ollama all serve, so the same adapter is either
    fully local or a third-party vendor depending entirely on where it points. The
    base URL is the only thing that knows which.
    """
    if provider == "ollama":
        return False
    if provider == "claude":
        return True
    host = urlsplit(settings.openai_base_url).hostname if settings.openai_base_url else None
    return host not in LOCAL_HOSTS  # no base URL -> api.openai.com -> cloud


def _ensure_allowed(provider: ProviderName, settings: Settings, half: str) -> None:
    """Refuse a cloud provider when running fully local (LOCAL_ONLY).

    Checked per half: LOCAL_ONLY with a local LLM and cloud embeddings refuses the
    embeddings and leaves the LLM alone, rather than failing the whole app.

    An unrecognised name is rejected here as unknown rather than being treated as a
    cloud endpoint — pydantic keeps it out via the Literal, but a name assigned after
    construction must still fail as ValueError and not as a LOCAL_ONLY refusal.
    """
    if provider not in ("ollama", "claude", "openai"):
        raise ValueError(f"Unknown provider: {provider!r}")
    if settings.local_only and _is_cloud(provider, settings):
        where = settings.openai_base_url or "the vendor default endpoint"
        raise RuntimeError(
            f"LOCAL_ONLY is enabled: the {provider!r} provider ({where}) is disabled "
            f"for the {half}. Set LOCAL_ONLY=false to allow it, or point "
            f"{half.upper().replace(' ', '_')} at a local backend."
        )


def get_embeddings(settings: Settings) -> Embeddings:
    provider = settings.active_embed_provider
    _ensure_allowed(provider, settings, "embeddings")

    if provider == "ollama":
        from langchain_huggingface import HuggingFaceEmbeddings

        from app.device import resolve_device

        # Local sentence-transformers model; downloads once, then runs offline.
        # device: "auto" picks cuda -> mps -> cpu (see app/device.py / EMBED_DEVICE).
        return HuggingFaceEmbeddings(
            model_name=settings.hf_embed_model,
            model_kwargs={"device": resolve_device(settings.embed_device)},
        )

    if provider == "claude":
        from langchain_voyageai import VoyageAIEmbeddings

        return VoyageAIEmbeddings(
            model=settings.voyage_model,
            **_api_key_kwarg(settings.voyage_api_key),
        )

    if provider == "openai":
        from langchain_openai import OpenAIEmbeddings

        return OpenAIEmbeddings(
            model=settings.openai_embed_model,
            **_openai_endpoint_kwargs(settings),
        )

    raise ValueError(f"Unknown provider: {provider!r}")


def get_llm(settings: Settings) -> BaseChatModel:
    provider = settings.active_llm_provider
    _ensure_allowed(provider, settings, "llm")

    if provider == "ollama":
        from langchain_ollama import ChatOllama

        return ChatOllama(
            model=settings.ollama_llm_model,
            base_url=settings.ollama_base_url,
            temperature=0,
            num_predict=settings.max_tokens,
        )

    if provider == "claude":
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

    if provider == "openai":
        from langchain_openai import ChatOpenAI

        return ChatOpenAI(
            model=settings.openai_llm_model,
            temperature=0,
            max_completion_tokens=settings.max_tokens,
            **_openai_endpoint_kwargs(settings),
        )

    raise ValueError(f"Unknown provider: {provider!r}")


def _openai_endpoint_kwargs(settings: Settings) -> dict[str, Any]:
    """Endpoint + credentials shared by the OpenAI chat and embedding clients.

    A local server usually wants no key at all, but the client library requires one
    to be present, so a placeholder goes out rather than letting construction fail
    on a backend that will ignore it.
    """
    kwargs: dict[str, Any] = {"api_key": SecretStr(settings.openai_api_key or "not-needed")}
    if settings.openai_base_url:
        kwargs["base_url"] = settings.openai_base_url
    return kwargs
