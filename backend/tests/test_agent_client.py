import json

import httpx

from src.services.agent_client import AgentClient


_RealClient = httpx.Client  # captured before any monkeypatching of httpx.Client below


def _mock_client(handler):
    return _RealClient(transport=httpx.MockTransport(handler), base_url="http://agents.test")


def test_invoke_posts_expected_body_and_parses_response(monkeypatch):
    captured = {}

    def handler(request: httpx.Request) -> httpx.Response:
        captured["path"] = request.url.path
        captured["body"] = json.loads(request.content)
        return httpx.Response(200, json={"response": "PCOS can cause irregular periods.", "trace": {"tool_calls": []}})

    client = AgentClient(base_url="http://agents.test")
    monkeypatch.setattr(httpx, "Client", lambda *args, **kwargs: _mock_client(handler))

    result = client.invoke("Can PCOS cause irregular periods?", user_id="u1", session_id="s1")

    assert captured["path"] == "/invoke"
    assert captured["body"] == {
        "message": "Can PCOS cause irregular periods?",
        "user_id": "u1",
        "session_id": "s1",
    }
    assert result["response"] == "PCOS can cause irregular periods."


def test_invoke_raises_on_http_error(monkeypatch):
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(500, json={"detail": "boom"})

    client = AgentClient(base_url="http://agents.test")
    monkeypatch.setattr(httpx, "Client", lambda *args, **kwargs: _mock_client(handler))

    try:
        client.invoke("anything", user_id="u1")
        assert False, "expected HTTPStatusError"
    except httpx.HTTPStatusError:
        pass
