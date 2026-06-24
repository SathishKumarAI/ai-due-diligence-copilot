from langchain_core.documents import Document

from app.rag import RagEngine


def _engine_with(docs):
    class _Store:
        def similarity_search(self, q, k):  # noqa: ANN001
            return docs[:k]

    class _LLM:
        def invoke(self, messages):  # noqa: ANN001
            from langchain_core.messages import AIMessage

            return AIMessage(content="The valuation is 220M [2].")

    return RagEngine(_Store(), _LLM(), top_k=3, provider="fake")


def test_citations_map_used_markers_to_sources():
    docs = [
        Document(page_content="aaa", metadata={"source": "a.md", "page": 1}),
        Document(page_content="bbb 220M", metadata={"source": "b.md", "page": 2}),
        Document(page_content="ccc", metadata={"source": "c.md", "page": None}),
    ]
    result = _engine_with(docs).answer("valuation?")
    assert [c.marker for c in result.citations] == [2]
    assert result.citations[0].source == "b.md"
    assert result.citations[0].page == 2


def test_citations_fallback_to_all_when_no_markers(fake_engine, sample_docs):
    engine = fake_engine
    engine.llm.reply = "An answer with no markers at all."
    result = engine.answer("anything")
    # No [n] in the answer -> every retrieved chunk is returned as a traceable source.
    assert len(result.citations) == 3


def test_no_results_returns_guardrail():
    class _EmptyStore:
        def similarity_search(self, q, k):  # noqa: ANN001
            return []

    class _LLM:
        def invoke(self, messages):  # noqa: ANN001
            raise AssertionError("LLM should not be called when nothing retrieved")

    engine = RagEngine(_EmptyStore(), _LLM(), top_k=3, provider="fake")
    result = engine.answer("unknown")
    assert "do not cover" in result.answer
    assert result.citations == []
