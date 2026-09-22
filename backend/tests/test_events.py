from fastapi.testclient import TestClient
from src.main import app
from src.schemas.events import build_event

client = TestClient(app)


def test_build_event_generates_id_and_timestamp():
    event = build_event(event_type="SOURCE_OPENED", session_id="s1", knowledge_id="know_pcos_001")
    assert event["event_type"] == "SOURCE_OPENED"
    assert event["session_id"] == "s1"
    assert event["knowledge_id"] == "know_pcos_001"
    assert event["event_id"]
    assert event["occurred_at"]


def test_build_event_no_question_or_answer_text_field():
    event = build_event(event_type="QUESTION_ASKED", session_id="s1")
    assert "question_text" not in event
    assert "answer_text" not in event
    assert "message" not in event


def test_post_event_source_opened(monkeypatch):
    published = []
    monkeypatch.setattr("src.api.events.publish_event", lambda event: published.append(event))

    response = client.post(
        "/api/events",
        json={"event_type": "SOURCE_OPENED", "session_id": "s1", "knowledge_id": "know_pcos_001"},
    )
    assert response.status_code == 202
    assert len(published) == 1
    assert published[0]["event_type"] == "SOURCE_OPENED"
    assert published[0]["knowledge_id"] == "know_pcos_001"


def test_post_event_feedback_submitted(monkeypatch):
    published = []
    monkeypatch.setattr("src.api.events.publish_event", lambda event: published.append(event))

    response = client.post(
        "/api/events",
        json={"event_type": "FEEDBACK_SUBMITTED", "session_id": "s1", "trace_id": "t1", "rating": "up"},
    )
    assert response.status_code == 202
    assert published[0]["rating"] == "up"


def test_post_event_rejects_server_only_event_type():
    # QUESTION_ASKED/RESPONSE_GENERATED are server-published only (see events.py docstring) -
    # a client trying to fabricate one should fail validation, not silently succeed.
    response = client.post("/api/events", json={"event_type": "QUESTION_ASKED", "session_id": "s1"})
    assert response.status_code == 422


def test_post_event_rejects_invalid_rating():
    response = client.post(
        "/api/events",
        json={"event_type": "FEEDBACK_SUBMITTED", "session_id": "s1", "rating": "sideways"},
    )
    assert response.status_code == 422
