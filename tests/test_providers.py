import pytest

from app.cache import embedding_namespace
from app.config import Settings
from app.providers import get_embeddings, get_llm


def test_get_llm_ollama():
    from langchain_ollama import ChatOllama

    llm = get_llm(Settings(provider="ollama"))
    assert isinstance(llm, ChatOllama)


def test_get_llm_claude():
    from langchain_anthropic import ChatAnthropic

    # Cloud path is gated by LOCAL_ONLY; opt in explicitly to exercise it.
    llm = get_llm(Settings(provider="claude", anthropic_api_key="test-key", local_only=False))
    assert isinstance(llm, ChatAnthropic)


def test_claude_blocked_when_local_only():
    # Default LOCAL_ONLY=true must refuse the cloud provider for both LLM and embeddings.
    s = Settings(provider="claude", anthropic_api_key="test-key")
    assert s.local_only is True
    with pytest.raises(RuntimeError):
        get_llm(s)
    with pytest.raises(RuntimeError):
        get_embeddings(s)


def test_unknown_provider_raises():
    bad = Settings(provider="ollama")
    bad.provider = "bogus"  # type: ignore[assignment]
    with pytest.raises(ValueError):
        get_llm(bad)
    with pytest.raises(ValueError):
        get_embeddings(bad)


# --- the LLM/embedding split -------------------------------------------------


def test_split_defaults_to_the_single_provider_switch():
    """PROVIDER alone must keep working: both halves follow it when unset."""
    s = Settings(provider="claude")
    assert s.active_llm_provider == "claude"
    assert s.active_embed_provider == "claude"


def test_each_half_can_be_set_independently():
    s = Settings(provider="ollama", llm_provider="claude")
    assert s.active_llm_provider == "claude"
    assert s.active_embed_provider == "ollama"  # still follows PROVIDER


def test_mixed_local_llm_with_cloud_embeddings_is_gated_per_half():
    """LOCAL_ONLY refuses the cloud half only — the local half still resolves."""
    s = Settings(provider="ollama", embed_provider="claude", voyage_api_key="test-key")
    get_llm(s)  # local LLM: allowed
    with pytest.raises(RuntimeError):
        get_embeddings(s)  # cloud embeddings: refused


def test_active_model_names_follow_their_own_half():
    s = Settings(provider="ollama", llm_provider="claude")
    assert s.active_llm_model == s.anthropic_model
    assert s.active_embed_model == s.hf_embed_model


# --- the OpenAI-compatible adapter -------------------------------------------


def test_get_llm_openai():
    from langchain_openai import ChatOpenAI

    llm = get_llm(Settings(provider="openai", openai_api_key="test-key", local_only=False))
    assert isinstance(llm, ChatOpenAI)


def test_get_embeddings_openai():
    from langchain_openai import OpenAIEmbeddings

    emb = get_embeddings(Settings(provider="openai", openai_api_key="test-key", local_only=False))
    assert isinstance(emb, OpenAIEmbeddings)


def test_openai_default_base_url_is_cloud_and_blocked_when_local_only():
    s = Settings(provider="openai", openai_api_key="test-key")
    assert s.local_only is True
    with pytest.raises(RuntimeError):
        get_llm(s)
    with pytest.raises(RuntimeError):
        get_embeddings(s)


@pytest.mark.parametrize(
    "base_url",
    [
        "http://localhost:8000/v1",
        "http://127.0.0.1:1234/v1",
        "http://host.docker.internal:11434/v1",
    ],
)
def test_openai_against_a_local_endpoint_is_allowed_under_local_only(base_url):
    """vLLM / LM Studio / Ollama speak the OpenAI API on localhost. That is still local."""
    s = Settings(provider="openai", openai_api_key="not-needed", openai_base_url=base_url)
    assert s.local_only is True
    get_llm(s)
    get_embeddings(s)


def test_openai_against_a_remote_base_url_is_still_cloud():
    s = Settings(
        provider="openai",
        openai_api_key="test-key",
        openai_base_url="https://api.groq.com/openai/v1",
    )
    with pytest.raises(RuntimeError):
        get_llm(s)


# --- the vector store must not outlive the embedding model -------------------


def test_collection_name_changes_with_the_embedding_model():
    """Vectors from bge-small are meaningless to bge-large. Different model, different
    collection - otherwise Chroma silently serves the previous model's vectors."""
    small = Settings(provider="ollama", hf_embed_model="BAAI/bge-small-en-v1.5")
    large = Settings(provider="ollama", hf_embed_model="BAAI/bge-large-en-v1.5")
    assert small.active_collection_name != large.active_collection_name


def test_collection_name_changes_with_the_embedding_provider():
    local = Settings(provider="ollama")
    cloud = Settings(provider="claude")
    assert local.active_collection_name != cloud.active_collection_name


def test_collection_name_ignores_the_llm_half():
    """Swapping the generator does not invalidate the index."""
    a = Settings(provider="ollama", llm_provider="ollama")
    b = Settings(provider="ollama", llm_provider="claude")
    assert a.active_collection_name == b.active_collection_name


def test_collection_name_is_stable_for_identical_settings():
    assert Settings().active_collection_name == Settings().active_collection_name


@pytest.mark.parametrize(
    "settings",
    [
        Settings(),
        Settings(provider="claude"),
        Settings(provider="openai"),
        # A long HuggingFace id must not overflow Chroma's 63-character ceiling.
        Settings(provider="ollama", hf_embed_model="sentence-transformers/" + "x" * 120),
    ],
)
def test_collection_name_satisfies_chroma_constraints(settings):
    """Chroma: 3-63 chars, [a-zA-Z0-9._-], must start and end alphanumeric."""
    import re

    name = settings.active_collection_name
    assert 3 <= len(name) <= 63, name
    assert re.fullmatch(r"[a-zA-Z0-9][a-zA-Z0-9._-]*[a-zA-Z0-9]", name), name
    assert ".." not in name, name


# --- the embedding cache namespace follows the same half ---------------------


def test_embedding_namespace_follows_the_embed_half_not_the_llm_half():
    s = Settings(provider="ollama", llm_provider="claude")
    assert "bge-small" in embedding_namespace(s)
    assert "voyage" not in embedding_namespace(s)


def test_embedding_namespace_changes_with_the_embedding_model():
    small = Settings(hf_embed_model="BAAI/bge-small-en-v1.5")
    large = Settings(hf_embed_model="BAAI/bge-large-en-v1.5")
    assert embedding_namespace(small) != embedding_namespace(large)
