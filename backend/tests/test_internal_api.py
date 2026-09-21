from fastapi.testclient import TestClient

from src.config import get_settings
from src.main import app

client = TestClient(app)
API_KEY = get_settings().internal_api_key
HEADERS = {"X-Internal-Api-Key": API_KEY}


def test_missing_api_key_rejected():
    response = client.get("/internal/topics")
    assert response.status_code == 401


def test_wrong_api_key_rejected():
    response = client.get("/internal/topics", headers={"X-Internal-Api-Key": "wrong"})
    assert response.status_code == 401


def test_query_health_topics(monkeypatch):
    fake_topics = [{"topic_id": "pcos", "topic_name": "PCOS", "parent_category": "Hormonal Health", "description": ""}]
    monkeypatch.setattr("src.api.internal.repo.list_topics", lambda client, project: fake_topics)
    monkeypatch.setattr("src.api.internal.repo.get_bigquery_client", lambda: object())

    response = client.get("/internal/topics", headers=HEADERS)
    assert response.status_code == 200
    assert response.json() == fake_topics


def test_get_knowledge_record_found(monkeypatch):
    fake_record = {"knowledge_id": "know_pcos_001", "title": "What PCOS is"}
    monkeypatch.setattr("src.api.internal.repo.get_knowledge_record", lambda client, project, kid: fake_record)
    monkeypatch.setattr("src.api.internal.repo.get_bigquery_client", lambda: object())

    response = client.get("/internal/knowledge/know_pcos_001", headers=HEADERS)
    assert response.status_code == 200
    assert response.json() == fake_record


def test_get_knowledge_record_not_found(monkeypatch):
    monkeypatch.setattr("src.api.internal.repo.get_knowledge_record", lambda client, project, kid: None)
    monkeypatch.setattr("src.api.internal.repo.get_bigquery_client", lambda: object())

    response = client.get("/internal/knowledge/does_not_exist", headers=HEADERS)
    assert response.status_code == 404


def test_check_content_eligibility(monkeypatch):
    monkeypatch.setattr("src.api.internal.repo.check_eligibility", lambda client, project, kid: False)
    monkeypatch.setattr("src.api.internal.repo.get_bigquery_client", lambda: object())

    response = client.get("/internal/knowledge/know_mc_007/eligibility", headers=HEADERS)
    assert response.status_code == 200
    assert response.json() == {"knowledge_id": "know_mc_007", "ai_eligible": False}


def test_search_knowledge_route(monkeypatch):
    fake_results = [{"knowledge_id": "know_pcos_004", "hybrid_score": 0.93}]
    monkeypatch.setattr("src.api.internal.search_knowledge", lambda *args, **kwargs: fake_results)
    monkeypatch.setattr("src.api.internal.repo.get_bigquery_client", lambda: object())
    monkeypatch.setattr("src.api.internal.get_genai_client", lambda: object())

    response = client.post(
        "/internal/search-knowledge", headers=HEADERS, json={"query": "Can PCOS cause irregular periods?"}
    )
    assert response.status_code == 200
    assert response.json() == fake_results


def test_find_related_topics(monkeypatch):
    fake_related = [{"topic_id": "menopause", "topic_name": "Menopause", "parent_category": "Hormonal Health"}]
    monkeypatch.setattr("src.api.internal.repo.list_related_topics", lambda client, project, topic_id, limit: fake_related)
    monkeypatch.setattr("src.api.internal.repo.get_bigquery_client", lambda: object())

    response = client.get("/internal/topics/pcos/related", headers=HEADERS)
    assert response.status_code == 200
    assert response.json() == fake_related
