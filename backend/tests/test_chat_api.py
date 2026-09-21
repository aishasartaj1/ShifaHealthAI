from fastapi.testclient import TestClient

from src.api.chat import extract_candidate_knowledge_ids
from src.main import app

client = TestClient(app)


def test_extract_candidate_knowledge_ids_from_search_knowledge_calls():
    trace = {
        "tool_calls": [
            {"tool": "search_knowledge", "result_summary": {"candidate_knowledge_ids": ["a", "b"]}},
            {"tool": "query_health_topics", "result_summary": {"topic_count": 6}},
        ]
    }
    assert extract_candidate_knowledge_ids(trace) == ["a", "b"]


def test_extract_candidate_knowledge_ids_dedupes_across_calls():
    trace = {
        "tool_calls": [
            {"tool": "search_knowledge", "result_summary": {"candidate_knowledge_ids": ["a", "b"]}},
            {"tool": "search_knowledge", "result_summary": {"candidate_knowledge_ids": ["b", "c"]}},
        ]
    }
    assert extract_candidate_knowledge_ids(trace) == ["a", "b", "c"]


def test_extract_candidate_knowledge_ids_empty_trace():
    assert extract_candidate_knowledge_ids({}) == []
    assert extract_candidate_knowledge_ids({"tool_calls": []}) == []


def test_chat_endpoint_builds_sources_and_related_topics(monkeypatch):
    fake_agent_result = {
        "response": "PCOS can cause irregular periods (Source: know_pcos_004).",
        "trace": {
            "tool_calls": [
                {"tool": "search_knowledge", "result_summary": {"candidate_knowledge_ids": ["know_pcos_004"]}}
            ],
            "total_latency_ms": 1234.5,
        },
    }
    fake_knowledge_record = {
        "knowledge_id": "know_pcos_004",
        "topic_id": "pcos",
        "topic_name": "PCOS",
        "source_id": "src_acog_pcos",
        "source_name": "ACOG",
        "title": "How PCOS relates to irregular periods",
        "last_reviewed_date": "2025-10-15",
    }
    fake_source_record = {"source_id": "src_acog_pcos", "url": "https://www.acog.org/..."}
    fake_related = [{"topic_id": "menopause", "topic_name": "Menopause", "parent_category": "Hormonal Health"}]

    published = []
    monkeypatch.setattr("src.api.chat.AgentClient.invoke", lambda self, message, user_id, session_id: fake_agent_result)
    monkeypatch.setattr("src.api.chat.repo.get_bigquery_client", lambda: object())
    monkeypatch.setattr("src.api.chat.repo.get_knowledge_record", lambda client, project, kid: fake_knowledge_record)
    monkeypatch.setattr("src.api.chat.repo.get_source_record", lambda client, project, sid: fake_source_record)
    monkeypatch.setattr(
        "src.api.chat.repo.list_related_topics", lambda client, project, topic_id, limit: fake_related
    )
    monkeypatch.setattr("src.api.chat.publish_event", lambda event: published.append(event))

    response = client.post("/api/chat", json={"message": "Can PCOS cause irregular periods?"})
    assert response.status_code == 200
    body = response.json()
    assert body["answer"] == fake_agent_result["response"]
    assert body["sources"] == [
        {
            "knowledge_id": "know_pcos_004",
            "title": "How PCOS relates to irregular periods",
            "source_name": "ACOG",
            "source_url": "https://www.acog.org/...",
            "last_reviewed_date": "2025-10-15",
        }
    ]
    assert body["related_topics"] == [{"topic_id": "menopause", "topic_name": "Menopause"}]
    assert body["disclaimer"] == "Educational information only; not a substitute for professional medical care."
    assert body["trace_id"]

    assert [e["event_type"] for e in published] == ["QUESTION_ASKED", "RESPONSE_GENERATED"]
    response_event = published[1]
    assert response_event["trace_id"] == body["trace_id"]
    assert response_event["source_count"] == 1
    assert response_event["latency_ms"] is not None


def test_chat_endpoint_handles_no_candidates(monkeypatch):
    fake_agent_result = {
        "response": "I can share general educational information but not a treatment plan.",
        "trace": {"tool_calls": [], "total_latency_ms": 500.0},
    }
    monkeypatch.setattr("src.api.chat.AgentClient.invoke", lambda self, message, user_id, session_id: fake_agent_result)
    monkeypatch.setattr("src.api.chat.repo.get_bigquery_client", lambda: object())
    monkeypatch.setattr("src.api.chat.publish_event", lambda event: None)

    response = client.post("/api/chat", json={"message": "What medication should I take?"})
    assert response.status_code == 200
    body = response.json()
    assert body["sources"] == []
    assert body["related_topics"] == []
