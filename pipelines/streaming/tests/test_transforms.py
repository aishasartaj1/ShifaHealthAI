from datetime import datetime, timezone

from transforms import OUTPUT_FIELDS, normalize_event, validate_event

VALID_EVENT = {
    "event_id": "e1",
    "event_type": "QUESTION_ASKED",
    "session_id": "s1",
    "trace_id": None,
    "occurred_at": "2026-09-21T08:00:00+00:00",
}


def test_validate_event_valid():
    assert validate_event(VALID_EVENT) == (True, None)


def test_validate_event_missing_required_field():
    event = {**VALID_EVENT, "session_id": ""}
    ok, reason = validate_event(event)
    assert not ok
    assert "session_id" in reason


def test_validate_event_invalid_event_type():
    event = {**VALID_EVENT, "event_type": "SOMETHING_ELSE"}
    ok, reason = validate_event(event)
    assert not ok
    assert "event_type" in reason


def test_validate_event_invalid_rating():
    event = {**VALID_EVENT, "event_type": "FEEDBACK_SUBMITTED", "rating": "sideways"}
    ok, reason = validate_event(event)
    assert not ok
    assert "rating" in reason


def test_validate_event_valid_rating():
    event = {**VALID_EVENT, "event_type": "FEEDBACK_SUBMITTED", "rating": "up"}
    assert validate_event(event) == (True, None)


def test_validate_event_unparseable_timestamp():
    event = {**VALID_EVENT, "occurred_at": "not-a-timestamp"}
    ok, reason = validate_event(event)
    assert not ok
    assert "occurred_at" in reason


def test_validate_event_accepts_native_datetime():
    event = {**VALID_EVENT, "occurred_at": datetime.now(timezone.utc)}
    assert validate_event(event) == (True, None)


def test_normalize_event_fills_all_output_fields():
    normalized = normalize_event(VALID_EVENT)
    assert set(normalized.keys()) == set(OUTPUT_FIELDS)
    assert normalized["latency_ms"] is None
    assert normalized["knowledge_id"] is None


def test_normalize_event_drops_unexpected_fields():
    event = {**VALID_EVENT, "question_text": "this should never be stored"}
    normalized = normalize_event(event)
    assert "question_text" not in normalized
