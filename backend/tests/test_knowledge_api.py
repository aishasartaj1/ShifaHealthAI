from fastapi.testclient import TestClient
from src.main import app

client = TestClient(app)


def test_get_knowledge_found(monkeypatch):
    fake_record = {"knowledge_id": "know_pcos_001", "title": "What PCOS is"}
    monkeypatch.setattr("src.api.knowledge.repo.get_knowledge_record", lambda client, project, kid: fake_record)
    monkeypatch.setattr("src.api.knowledge.repo.get_bigquery_client", lambda: object())

    response = client.get("/api/knowledge/know_pcos_001")
    assert response.status_code == 200
    assert response.json() == fake_record


def test_get_knowledge_not_found(monkeypatch):
    monkeypatch.setattr("src.api.knowledge.repo.get_knowledge_record", lambda client, project, kid: None)
    monkeypatch.setattr("src.api.knowledge.repo.get_bigquery_client", lambda: object())

    response = client.get("/api/knowledge/does_not_exist")
    assert response.status_code == 404


def test_get_source_found(monkeypatch):
    fake_source = {"source_id": "src_acog_pcos", "source_name": "ACOG"}
    monkeypatch.setattr("src.api.knowledge.repo.get_source_record", lambda client, project, sid: fake_source)
    monkeypatch.setattr("src.api.knowledge.repo.get_bigquery_client", lambda: object())

    response = client.get("/api/sources/src_acog_pcos")
    assert response.status_code == 200
    assert response.json() == fake_source


def test_get_source_not_found(monkeypatch):
    monkeypatch.setattr("src.api.knowledge.repo.get_source_record", lambda client, project, sid: None)
    monkeypatch.setattr("src.api.knowledge.repo.get_bigquery_client", lambda: object())

    response = client.get("/api/sources/does_not_exist")
    assert response.status_code == 404
