from fastapi.testclient import TestClient
from src.main import app

client = TestClient(app)


def test_list_topics(monkeypatch):
    fake_topics = [{"topic_id": "pcos", "topic_name": "PCOS", "parent_category": "Hormonal Health", "description": ""}]
    monkeypatch.setattr("src.api.topics.repo.list_topics", lambda client, project: fake_topics)
    monkeypatch.setattr("src.api.topics.repo.get_bigquery_client", lambda: object())

    response = client.get("/api/topics")
    assert response.status_code == 200
    assert response.json() == fake_topics


def test_list_topic_knowledge(monkeypatch):
    fake_records = [{"knowledge_id": "know_pcos_001", "title": "What PCOS is"}]
    monkeypatch.setattr(
        "src.api.topics.repo.list_knowledge_by_topic", lambda client, project, topic_id: fake_records
    )
    monkeypatch.setattr("src.api.topics.repo.get_bigquery_client", lambda: object())

    response = client.get("/api/topics/pcos/knowledge")
    assert response.status_code == 200
    assert response.json() == fake_records
