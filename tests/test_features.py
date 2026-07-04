"""Unit + integration tests for F16–F19 (hybrid retrieval, reranker, upload,
conversation memory + feedback). All offline — fakes only, no model downloads."""

from __future__ import annotations

import json

import pytest
from fastapi.testclient import TestClient
from langchain_core.documents import Document
from langchain_core.messages import AIMessage, AIMessageChunk

from app.feedback import feedback_summary, record_feedback
from app.rag import RagEngine, Turn
from app.rerank import NoOpReranker
from app.retrieval import (
    BM25Index,
    DenseRetriever,
    HybridRetriever,
    reciprocal_rank_fusion,
)

# --- F16: BM25 + RRF fusion ---------------------------------------------------


def test_bm25_ranks_exact_term_match_first():
    # Domain-neutral so this engine test is identical across all three repos.
    docs = [
        Document(page_content="the exact term appears here in this passage", metadata={"source": "a"}),
        Document(page_content="an unrelated passage about other topics", metadata={"source": "b"}),
    ]
    bm25 = BM25Index(docs)
    hits = bm25.search("exact term", k=2)
    assert hits, "BM25 should find lexical matches"
    assert hits[0].metadata["source"] == "a"


def test_bm25_keeps_figures_whole():
    docs = [
        Document(page_content="revenue was 12.4 million", metadata={"source": "a"}),
        Document(page_content="growth was strong this year", metadata={"source": "b"}),
    ]
    bm25 = BM25Index(docs)
    hits = bm25.search("12.4", k=2)
    assert hits[0].metadata["source"] == "a"


def test_bm25_empty_corpus_returns_nothing():
    assert BM25Index([]).search("anything", k=5) == []


def test_rrf_rewards_agreement_across_rankings():
    a = Document(page_content="A", metadata={"source": "a"})
    b = Document(page_content="B", metadata={"source": "b"})
    c = Document(page_content="C", metadata={"source": "c"})
    # b appears in both lists (top of one), a and c in only one each → b wins.
    fused = reciprocal_rank_fusion([[a, b], [b, c]], k=3, rrf_k=1)
    assert fused[0].metadata["source"] == "b"


def test_hybrid_unions_both_arms(fake_store, sample_docs):
    bm25 = BM25Index(sample_docs)
    hybrid = HybridRetriever(fake_store, bm25, fetch_k=10, rrf_k=60)
    hits = hybrid.retrieve("concentration risk ARR", k=3)
    assert hits
    assert all(isinstance(h, Document) for h in hits)


# --- F17: reranker ------------------------------------------------------------


class ReverseReranker:
    """Deterministic fake: reverses candidate order, trims to top_n."""

    def rerank(self, query, docs, top_n):  # noqa: ANN001
        return list(reversed(docs))[:top_n]


def test_reranker_reorders_and_trims():
    docs = [Document(page_content=str(i), metadata={"source": str(i)}) for i in range(5)]
    out = ReverseReranker().rerank("q", docs, 2)
    assert [d.page_content for d in out] == ["4", "3"]


def test_noop_reranker_preserves_order_and_trims():
    docs = [Document(page_content=str(i), metadata={"source": str(i)}) for i in range(5)]
    out = NoOpReranker().rerank("q", docs, 3)
    assert [d.page_content for d in out] == ["0", "1", "2"]


def test_engine_applies_reranker_before_generation(fake_store):
    from tests.conftest import FakeChat

    engine = RagEngine(
        fake_store,
        FakeChat(),
        top_k=1,
        retriever=DenseRetriever(fake_store),
        reranker=ReverseReranker(),
        fetch_k=3,
    )
    # With fetch_k=3 then rerank→reverse→top_k=1, exactly one doc reaches the LLM.
    ans = engine.answer("valuation?")
    assert len(ans.citations) == 1


# --- F19: conversation memory -------------------------------------------------


class CondensingChat:
    """Fake chat: condense calls return a standalone question; answer calls a reply."""

    def invoke(self, messages):  # noqa: ANN001
        system = messages[0][1]
        if "standalone question" in system:
            return AIMessage(content="What is the post money valuation?")
        return AIMessage(content="The valuation is grounded [1].")

    def stream(self, messages):  # noqa: ANN001
        yield AIMessageChunk(content="grounded [1]")


def test_condense_passthrough_without_history(fake_store):
    engine = RagEngine(fake_store, CondensingChat(), top_k=2)
    assert engine._condense("ARR?", None) == "ARR?"
    assert engine._condense("ARR?", []) == "ARR?"


def test_condense_rewrites_followup_with_history(fake_store):
    engine = RagEngine(fake_store, CondensingChat(), top_k=2)
    history = [
        Turn(role="user", content="Tell me about the term sheet"),
        Turn(role="assistant", content="It covers valuation and preferences [1]."),
    ]
    rewritten = engine._condense("and its valuation?", history)
    assert rewritten == "What is the post money valuation?"


def test_answer_records_condense_timing_when_history_present(fake_store):
    engine = RagEngine(fake_store, CondensingChat(), top_k=2)
    history = [Turn(role="user", content="term sheet?")]
    ans = engine.answer("and valuation?", history=history)
    assert "condense_ms" in ans.timings_ms
    assert ans.question == "and valuation?"  # original question is what we answer


# --- F19: feedback store ------------------------------------------------------


def test_record_and_summarize_feedback(tmp_path):
    path = tmp_path / "feedback.jsonl"
    record_feedback(path, question="q1", answer="a1", rating="up")
    record_feedback(path, question="q2", answer="a2", rating="down", comment="wrong")
    record_feedback(path, question="q3", answer="a3", rating="up")
    summary = feedback_summary(path)
    assert summary == {"up": 2, "down": 1, "total": 3}
    rows = [json.loads(line) for line in path.read_text().splitlines()]
    assert rows[1]["comment"] == "wrong"
    assert "ts" in rows[0]


def test_feedback_summary_missing_file(tmp_path):
    assert feedback_summary(tmp_path / "none.jsonl") == {"up": 0, "down": 0, "total": 0}


# --- F18: incremental ingest --------------------------------------------------


def test_add_file_to_store_indexes_and_is_idempotent(fake_store, tmp_path):
    from app.config import settings
    from app.ingest import add_file_to_store

    f = tmp_path / "memo.md"
    f.write_text("Net dollar retention was 121 percent in the latest quarter.")
    n1 = add_file_to_store(fake_store, f, settings)
    assert n1 >= 1
    # Re-upload replaces, does not duplicate: total chunks for source stays equal.
    n2 = add_file_to_store(fake_store, f, settings)
    assert n2 == n1
    hits = fake_store.similarity_search("net dollar retention", k=3)
    assert any("retention" in h.page_content.lower() for h in hits)


def test_add_file_rejects_unsupported_type(fake_store, tmp_path):
    from app.config import settings
    from app.ingest import add_file_to_store

    f = tmp_path / "data.csv"
    f.write_text("a,b,c")
    with pytest.raises(ValueError, match="Unsupported"):
        add_file_to_store(fake_store, f, settings)


def test_add_file_rejects_empty(fake_store, tmp_path):
    from app.config import settings
    from app.ingest import add_file_to_store

    f = tmp_path / "blank.txt"
    f.write_text("   \n  ")
    with pytest.raises(ValueError, match="no readable text"):
        add_file_to_store(fake_store, f, settings)


# --- API integration: upload, feedback, ask-with-history ----------------------


@pytest.fixture
def api_client(monkeypatch, fake_engine, tmp_path):
    import app.main as main
    from app.config import settings

    monkeypatch.setattr(settings, "data_dir", tmp_path)
    monkeypatch.setattr(settings, "feedback_path", tmp_path / "feedback.jsonl")
    monkeypatch.setattr(main, "build_engine", lambda: fake_engine)
    main.app.dependency_overrides[main.get_engine] = lambda: fake_engine
    with TestClient(main.app) as c:
        yield c
    main.app.dependency_overrides.clear()


def test_upload_endpoint_indexes_text(api_client):
    body = b"Gross margin expanded to 78 percent this fiscal year."
    r = api_client.post("/v1/upload?filename=margins.md", content=body)
    assert r.status_code == 200, r.text
    data = r.json()
    assert data["filename"] == "margins.md"
    assert data["chunks_added"] >= 1


def test_upload_rejects_unsupported_type(api_client):
    r = api_client.post("/v1/upload?filename=evil.exe", content=b"MZ...")
    assert r.status_code == 415


def test_upload_rejects_empty_body(api_client):
    r = api_client.post("/v1/upload?filename=empty.md", content=b"")
    assert r.status_code == 400


def test_upload_sanitizes_path_traversal(api_client, tmp_path):
    r = api_client.post("/v1/upload?filename=../../etc/passwd.txt", content=b"hello world text")
    assert r.status_code == 200
    # Saved as a basename inside the uploads dir, never outside data_dir.
    assert (tmp_path / "uploads" / "passwd.txt").exists()


def test_feedback_endpoint_persists(api_client, tmp_path):
    r = api_client.post(
        "/v1/feedback",
        json={"question": "ARR?", "answer": "12.4M [1]", "rating": "up"},
    )
    assert r.status_code == 200
    assert r.json() == {"ok": True, "up": 1, "down": 0, "total": 1}
    assert (tmp_path / "feedback.jsonl").exists()


def test_feedback_rejects_bad_rating(api_client):
    r = api_client.post(
        "/v1/feedback",
        json={"question": "q", "answer": "a", "rating": "maybe"},
    )
    assert r.status_code == 422


def test_ask_accepts_history(api_client):
    r = api_client.post(
        "/v1/ask",
        json={
            "question": "and its valuation?",
            "history": [
                {"role": "user", "content": "tell me about the term sheet"},
                {"role": "assistant", "content": "It sets the terms [1]."},
            ],
        },
    )
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["answer"]
    assert "condense_ms" in body["timings_ms"]
