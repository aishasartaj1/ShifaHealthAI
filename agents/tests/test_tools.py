"""tools.py just builds HTTP requests to backend and parses responses — tested here with
httpx.MockTransport so no real backend or GCP credentials are needed."""

import json
from types import SimpleNamespace

import httpx

from src import tools


def _mock_client(handler):
    return httpx.Client(transport=httpx.MockTransport(handler), base_url="http://backend.test")


# environment="cloud" (not "dev") for these two: they specifically test the fetch_id_token path,
# which _auth_headers now skips entirely when environment=="dev" (see its docstring for why).
FAKE_SETTINGS = SimpleNamespace(
    backend_base_url="http://backend.test", internal_api_key="dev-key", environment="cloud"
)
FAKE_DEV_SETTINGS = SimpleNamespace(
    backend_base_url="http://backend.test", internal_api_key="dev-key", environment="dev"
)


def test_auth_headers_skips_id_token_attempt_in_local_dev(monkeypatch):
    def _fail_if_called(*args, **kwargs):
        raise AssertionError("fetch_id_token should not be called when environment == 'dev'")

    monkeypatch.setattr(tools.google_id_token, "fetch_id_token", _fail_if_called)
    headers = tools._auth_headers(FAKE_DEV_SETTINGS)
    assert headers == {"X-Internal-Api-Key": "dev-key"}


def test_auth_headers_falls_back_to_shared_secret_when_no_id_token(monkeypatch):
    # Deployed, but ID-token minting still failed for some reason - the real failure mode this
    # fallback exists for, not a hypothetical.
    def _raise(*args, **kwargs):
        raise Exception("no service account credentials available")

    monkeypatch.setattr(tools.google_id_token, "fetch_id_token", _raise)
    headers = tools._auth_headers(FAKE_SETTINGS)
    assert headers == {"X-Internal-Api-Key": "dev-key"}


def test_auth_headers_attaches_bearer_token_when_available(monkeypatch):
    monkeypatch.setattr(tools.google_id_token, "fetch_id_token", lambda request, audience: "real-id-token")
    headers = tools._auth_headers(FAKE_SETTINGS)
    assert headers["Authorization"] == "Bearer real-id-token"
    assert headers["X-Internal-Api-Key"] == "dev-key"  # still sent - defense in depth


def test_search_knowledge_posts_expected_body(monkeypatch):
    captured = {}

    def handler(request: httpx.Request) -> httpx.Response:
        captured["method"] = request.method
        captured["path"] = request.url.path
        captured["body"] = json.loads(request.content)
        return httpx.Response(200, json=[{"knowledge_id": "know_pcos_004", "hybrid_score": 0.93}])

    monkeypatch.setattr(tools, "_client", lambda: _mock_client(handler))

    result = tools.search_knowledge("Can PCOS cause irregular periods?")

    assert captured["method"] == "POST"
    assert captured["path"] == "/internal/search-knowledge"
    assert captured["body"] == {"query": "Can PCOS cause irregular periods?", "topic": None, "top_n": 5}
    assert result == {"results": [{"knowledge_id": "know_pcos_004", "hybrid_score": 0.93}]}


def test_search_knowledge_passes_topic_filter(monkeypatch):
    captured = {}

    def handler(request: httpx.Request) -> httpx.Response:
        captured["body"] = json.loads(request.content)
        return httpx.Response(200, json=[])

    monkeypatch.setattr(tools, "_client", lambda: _mock_client(handler))
    tools.search_knowledge("What is PCOS", topic="pcos")
    assert captured["body"]["topic"] == "pcos"


def test_get_knowledge_record_found(monkeypatch):
    def handler(request: httpx.Request) -> httpx.Response:
        assert request.url.path == "/internal/knowledge/know_pcos_001"
        return httpx.Response(200, json={"knowledge_id": "know_pcos_001", "title": "What PCOS is"})

    monkeypatch.setattr(tools, "_client", lambda: _mock_client(handler))
    result = tools.get_knowledge_record("know_pcos_001")
    assert result == {"knowledge_id": "know_pcos_001", "title": "What PCOS is"}


def test_get_knowledge_record_not_found(monkeypatch):
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(404, json={"detail": "not found"})

    monkeypatch.setattr(tools, "_client", lambda: _mock_client(handler))
    result = tools.get_knowledge_record("does_not_exist")
    assert result == {"error": "Unknown knowledge_id 'does_not_exist'"}


def test_get_source_metadata_not_found(monkeypatch):
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(404, json={"detail": "not found"})

    monkeypatch.setattr(tools, "_client", lambda: _mock_client(handler))
    result = tools.get_source_metadata("does_not_exist")
    assert result == {"error": "Unknown source_id 'does_not_exist'"}


def test_check_content_eligibility(monkeypatch):
    def handler(request: httpx.Request) -> httpx.Response:
        assert request.url.path == "/internal/knowledge/know_mc_007/eligibility"
        return httpx.Response(200, json={"knowledge_id": "know_mc_007", "ai_eligible": False})

    monkeypatch.setattr(tools, "_client", lambda: _mock_client(handler))
    result = tools.check_content_eligibility("know_mc_007")
    assert result == {"knowledge_id": "know_mc_007", "ai_eligible": False}


def test_query_health_topics(monkeypatch):
    def handler(request: httpx.Request) -> httpx.Response:
        assert request.url.path == "/internal/topics"
        return httpx.Response(200, json=[{"topic_id": "pcos", "topic_name": "PCOS"}])

    monkeypatch.setattr(tools, "_client", lambda: _mock_client(handler))
    result = tools.query_health_topics()
    assert result == {"topics": [{"topic_id": "pcos", "topic_name": "PCOS"}]}


def test_find_related_topics(monkeypatch):
    def handler(request: httpx.Request) -> httpx.Response:
        assert request.url.path == "/internal/topics/pcos/related"
        return httpx.Response(200, json=[{"topic_id": "menopause", "topic_name": "Menopause"}])

    monkeypatch.setattr(tools, "_client", lambda: _mock_client(handler))
    result = tools.find_related_topics("pcos")
    assert result == {"related_topics": [{"topic_id": "menopause", "topic_name": "Menopause"}]}
