import pytest

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
