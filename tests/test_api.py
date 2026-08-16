"""Integration tests via FastAPI TestClient.

We stop the real engine from being built at startup (it would download an
embedding model) and inject the fake engine through the dependency override.
"""

from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

# The `client` fixture lives in conftest.py — test_grounding.py needs it too. The auth
# test below still builds its own client, because it has to construct one *after*
# monkeypatching the API key into settings.


def test_health_is_public(client):
    r = client.get("/health")
    assert r.status_code == 200
    assert r.json()["status"] == "ok"


def test_ask_returns_answer_with_citations(client):
    r = client.post("/v1/ask", json={"question": "What is the valuation?"})
    assert r.status_code == 200
    body = r.json()
    assert body["answer"]
    assert len(body["citations"]) >= 1
    assert "retrieve_ms" in body["timings_ms"]


def test_metrics_endpoint_exposes_prometheus(client):
    client.post("/v1/ask", json={"question": "ARR?"})
    r = client.get("/metrics")
    assert r.status_code == 200
    assert "rag_requests_total" in r.text


def test_validation_rejects_short_question(client):
    r = client.post("/v1/ask", json={"question": "x"})
    assert r.status_code == 422


def test_auth_required_when_api_key_set(monkeypatch, fake_engine):
    import app.main as main
    from app.config import settings

    monkeypatch.setattr(settings, "api_key", "secret")
    monkeypatch.setattr(main, "build_engine", lambda: fake_engine)
    main.app.dependency_overrides[main.get_engine] = lambda: fake_engine
    with TestClient(main.app) as c:
        assert c.post("/v1/ask", json={"question": "ARR?"}).status_code == 401
        ok = c.post("/v1/ask", json={"question": "ARR?"}, headers={"X-API-Key": "secret"})
        assert ok.status_code == 200
    main.app.dependency_overrides.clear()


def test_ready_is_not_ready_when_the_collection_cannot_be_counted(client, monkeypatch):
    # A re-ingest while the API is serving leaves it holding a stale Chroma handle: the
    # count raises, the endpoint returns the -1 sentinel, and reporting ready=true there
    # keeps an orchestrator routing traffic to an instance that has lost its index.
    import app.main as main

    class Dead:
        def count(self):
            raise RuntimeError("collection reset underneath us")

    monkeypatch.setattr(
        type(main.app.state.engine.vectorstore), "_collection", Dead(), raising=False
    )
    body = client.get("/ready").json()
    assert body["indexed_chunks"] == -1
    assert body["ready"] is False


def test_get_engine_reloads_itself_when_the_collection_was_replaced(monkeypatch, fake_engine):
    """A stale handle must heal, not 500 forever.

    `python -m app.ingest` is the documented reindex command and it runs out of process,
    so it resets the collection under a serving API. That used to poison the instance
    permanently: every request after it died with an opaque 500 and the web UI reported
    "Could not load the trace. Is the backend running?" while the backend was up. Only a
    restart recovered it. Hit for real during this session.
    """
    import app.main as main

    class Dead:
        def count(self):
            raise RuntimeError("collection reset underneath us")

    class DeadStore:
        _collection = Dead()

    stale = main.RagEngine(DeadStore(), fake_engine.llm, provider="stale")  # type: ignore[arg-type]
    monkeypatch.setattr(main.app.state, "engine", stale, raising=False)

    rebuilds = []

    def rebuild():
        rebuilds.append(1)
        return fake_engine

    monkeypatch.setattr(main, "build_engine", rebuild)

    got = main.get_engine()

    assert rebuilds == [1], "a dead collection handle should trigger exactly one rebuild"
    assert got is fake_engine
    assert main.app.state.engine is fake_engine, (
        "the healed engine must be kept, not rebuilt per call"
    )
    # The corpus changed underneath the process, so answers cached against the old index
    # must not be served against the new one.
    assert main.app.state.cache._fingerprint == main._corpus_fingerprint()


def test_get_engine_does_not_rebuild_a_healthy_engine(monkeypatch, fake_engine):
    """The self-heal must be triggered by a dead handle, never by ordinary traffic."""
    import app.main as main

    monkeypatch.setattr(main.app.state, "engine", fake_engine, raising=False)
    monkeypatch.setattr(
        main,
        "build_engine",
        lambda: pytest.fail("rebuilt a healthy engine"),  # type: ignore[arg-type,return-value]
    )

    assert main.get_engine() is fake_engine
