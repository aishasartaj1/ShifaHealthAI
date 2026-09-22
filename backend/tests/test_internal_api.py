from types import SimpleNamespace

from fastapi.testclient import TestClient
from src.api.internal import _verify_id_token
from src.config import get_settings
from src.main import app

client = TestClient(app)
API_KEY = get_settings().internal_api_key
HEADERS = {"X-Internal-Api-Key": API_KEY}

CONFIGURED_SETTINGS = SimpleNamespace(
    public_base_url="https://backend-abc123-uc.a.run.app",
    agents_service_account_email="shifahealth-agents@shifahealthai.iam.gserviceaccount.com",
)


def test_missing_api_key_rejected():
    response = client.get("/internal/topics")
    assert response.status_code == 401


def test_wrong_api_key_rejected():
    response = client.get("/internal/topics", headers={"X-Internal-Api-Key": "wrong"})
    assert response.status_code == 401


def test_verify_id_token_unconfigured_returns_false():
    # public_base_url / agents_service_account_email unset (the local-dev default) -> never even
    # attempts verification, so a Bearer token always falls through to the shared-secret check.
    unconfigured = SimpleNamespace(public_base_url="", agents_service_account_email="")
    assert _verify_id_token("any-token", unconfigured) is False


def test_verify_id_token_valid_matching_email(monkeypatch):
    monkeypatch.setattr(
        "src.api.internal.google_id_token.verify_oauth2_token",
        lambda token, request, audience: {"email": CONFIGURED_SETTINGS.agents_service_account_email},
    )
    assert _verify_id_token("valid-token", CONFIGURED_SETTINGS) is True


def test_verify_id_token_wrong_email(monkeypatch):
    monkeypatch.setattr(
        "src.api.internal.google_id_token.verify_oauth2_token",
        lambda token, request, audience: {"email": "someone-else@example.com"},
    )
    assert _verify_id_token("valid-token", CONFIGURED_SETTINGS) is False


def test_verify_id_token_verification_failure_returns_false(monkeypatch):
    def _raise(*args, **kwargs):
        raise ValueError("bad signature")

    monkeypatch.setattr("src.api.internal.google_id_token.verify_oauth2_token", _raise)
    assert _verify_id_token("garbage-token", CONFIGURED_SETTINGS) is False


def test_bearer_token_accepted_when_verification_succeeds(monkeypatch):
    monkeypatch.setattr("src.api.internal._verify_id_token", lambda token, settings: True)
    monkeypatch.setattr("src.api.internal.repo.list_topics", lambda client, project: [])
    monkeypatch.setattr("src.api.internal.repo.get_bigquery_client", lambda: object())

    response = client.get("/internal/topics", headers={"Authorization": "Bearer some-token"})
    assert response.status_code == 200


def test_bearer_token_rejected_when_verification_fails(monkeypatch):
    monkeypatch.setattr("src.api.internal._verify_id_token", lambda token, settings: False)

    response = client.get("/internal/topics", headers={"Authorization": "Bearer some-token"})
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
    monkeypatch.setattr(
        "src.api.internal.repo.list_related_topics", lambda client, project, topic_id, limit: fake_related
    )
    monkeypatch.setattr("src.api.internal.repo.get_bigquery_client", lambda: object())

    response = client.get("/internal/topics/pcos/related", headers=HEADERS)
    assert response.status_code == 200
    assert response.json() == fake_related
