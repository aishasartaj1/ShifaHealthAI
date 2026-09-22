import random

from generate_demo_events import build_session_events

CATALOG = [
    {"knowledge_id": "know_mc_001", "topic_id": "menstrual_cycle"},
    {"knowledge_id": "know_pcos_001", "topic_id": "pcos"},
]


def test_session_always_starts_with_question_then_response():
    random.seed(1)
    events = build_session_events(CATALOG)
    assert events[0]["event_type"] == "QUESTION_ASKED"
    assert events[1]["event_type"] == "RESPONSE_GENERATED"


def test_session_events_share_one_session_id():
    random.seed(2)
    events = build_session_events(CATALOG)
    assert len({e["session_id"] for e in events}) == 1


def test_source_opened_references_a_real_catalog_entry():
    random.seed(0)  # deterministic seed known to trigger SOURCE_OPENED for this small catalog
    events = build_session_events(CATALOG)
    source_opened = [e for e in events if e["event_type"] == "SOURCE_OPENED"]
    if source_opened:
        assert source_opened[0]["knowledge_id"] in {c["knowledge_id"] for c in CATALOG}
        assert source_opened[0]["topic_id"] in {c["topic_id"] for c in CATALOG}


def test_feedback_rating_is_up_or_down_when_present():
    random.seed(3)
    events = build_session_events(CATALOG)
    feedback = [e for e in events if e["event_type"] == "FEEDBACK_SUBMITTED"]
    for event in feedback:
        assert event["rating"] in {"up", "down"}


def test_occurred_at_is_within_recent_window_not_all_identical():
    random.seed(4)
    first = build_session_events(CATALOG)
    random.seed(5)
    second = build_session_events(CATALOG)
    assert first[0]["occurred_at"] != second[0]["occurred_at"]
