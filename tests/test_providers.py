import pytest

from app.config import Settings
from app.providers import get_embeddings, get_llm


def test_get_llm_ollama():
    from langchain_ollama import ChatOllama

    llm = get_llm(Settings(provider="ollama"))
    assert isinstance(llm, ChatOllama)


def test_get_llm_claude():
    from langchain_anthropic import ChatAnthropic

    llm = get_llm(Settings(provider="claude", anthropic_api_key="test-key"))
    assert isinstance(llm, ChatAnthropic)


def test_unknown_provider_raises():
    bad = Settings(provider="ollama")
    bad.provider = "bogus"  # type: ignore[assignment]
    with pytest.raises(ValueError):
        get_llm(bad)
    with pytest.raises(ValueError):
        get_embeddings(bad)
