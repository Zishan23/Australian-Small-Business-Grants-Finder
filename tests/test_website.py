"""Smoke tests for the local demo website's API.

Uses FastAPI's TestClient (backed by httpx), so this never starts a
real server or touches the network. Exercises the actual
MockQueryOrchestrator wired up in src/website/app.py, since that's
what a person opening the page locally will see.
"""

from fastapi.testclient import TestClient

from src.website.app import app

client = TestClient(app)


def test_health_reports_orchestrator():
    resp = client.get("/api/health")
    assert resp.status_code == 200
    body = resp.json()
    assert body["status"] == "ok"
    assert body["orchestrator"] == "MockQueryOrchestrator"


def test_index_serves_html():
    resp = client.get("/")
    assert resp.status_code == 200
    assert "text/html" in resp.headers["content-type"]
    assert "Grants Finder" in resp.text


def test_query_returns_mock_answer_with_citations():
    resp = client.post("/api/query", json={"question": "What grants can I get?"})
    assert resp.status_code == 200
    body = resp.json()
    assert body["is_mock"] is True
    assert body["answer"]
    assert len(body["citations"]) >= 1
    assert body["agents_used"]


def test_query_routes_compliance_style_question():
    resp = client.post("/api/query", json={"question": "What are my superannuation obligations?"})
    assert resp.status_code == 200
    body = resp.json()
    assert body["citations"][0]["source"] == "ato"


def test_query_rejects_missing_question():
    resp = client.post("/api/query", json={})
    assert resp.status_code == 422
