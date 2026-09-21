from fastapi.testclient import TestClient

from src.main import app
from src.services.trace_store import record_trace

client = TestClient(app)


def test_quality_endpoint(monkeypatch):
    fake_summary = {
        "total_knowledge_count": 38,
        "eligible_count": 33,
        "eligible_percentage": 86.8,
        "by_topic": [],
        "ineligible_records": [{"knowledge_id": "know_mc_007", "review_status": "NEEDS_REVIEW"}],
    }
    monkeypatch.setattr("src.api.admin.repo.get_quality_summary", lambda client, project: fake_summary)
    monkeypatch.setattr("src.api.admin.repo.get_bigquery_client", lambda: object())

    response = client.get("/api/admin/quality")
    assert response.status_code == 200
    assert response.json() == fake_summary


def test_list_agent_traces():
    record_trace("trace-list-test", {"trace_id": "trace-list-test", "question": "hi"})
    response = client.get("/api/admin/agents?limit=5")
    assert response.status_code == 200
    assert any(t["trace_id"] == "trace-list-test" for t in response.json())


def test_get_agent_trace_found():
    record_trace("trace-detail-test", {"trace_id": "trace-detail-test", "question": "hi"})
    response = client.get("/api/admin/agents/trace-detail-test")
    assert response.status_code == 200
    assert response.json()["trace_id"] == "trace-detail-test"


def test_get_agent_trace_not_found():
    response = client.get("/api/admin/agents/does-not-exist")
    assert response.status_code == 404


def test_analytics_endpoint(monkeypatch):
    fake_summary = {
        "global": {"total_questions_asked": 12.0, "avg_response_latency_ms": 15234.5},
        "by_topic": [{"topic_id": "pcos", "source_open_count": 3.0}],
        "computed_at": "2026-09-21T08:00:00+00:00",
    }
    monkeypatch.setattr("src.api.admin.repo.get_analytics_summary", lambda client, project: fake_summary)
    monkeypatch.setattr("src.api.admin.repo.get_bigquery_client", lambda: object())

    response = client.get("/api/admin/analytics")
    assert response.status_code == 200
    assert response.json() == fake_summary
