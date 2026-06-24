"""Integration tests via FastAPI TestClient.

We stop the real engine from being built at startup (it would download an
embedding model) and inject the fake engine through the dependency override.
"""
from __future__ import annotations

import pytest
from fastapi.testclient import TestClient


@pytest.fixture
def client(monkeypatch, fake_engine):
    import app.main as main

    # Don't build the real engine in lifespan (avoids model download).
    monkeypatch.setattr(main, "build_engine", lambda: fake_engine)
    main.app.dependency_overrides[main.get_engine] = lambda: fake_engine
    with TestClient(main.app) as c:
        yield c
    main.app.dependency_overrides.clear()


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
