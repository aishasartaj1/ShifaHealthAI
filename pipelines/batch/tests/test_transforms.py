from datetime import date

from transforms import (
    check_duplicates,
    compute_ai_eligible,
    enrich_knowledge,
    validate_knowledge,
    validate_review,
    validate_source,
    validate_topic,
)

TOPIC = {"topic_id": "pcos", "topic_name": "PCOS", "parent_category": "Hormonal Health", "description": ""}
SOURCE_ACTIVE = {
    "source_id": "src_a",
    "source_name": "Source A",
    "source_type": "government",
    "url": "https://example.gov/a",
    "source_status": "ACTIVE",
}
SOURCE_INACTIVE = {**SOURCE_ACTIVE, "source_id": "src_b", "source_status": "INACTIVE"}
KNOWLEDGE = {
    "knowledge_id": "know_1",
    "topic_id": "pcos",
    "source_id": "src_a",
    "title": "Title",
    "summary": "Summary",
    "review_status": "APPROVED",
    "content_status": "CURRENT",
    "published_date": "2025-01-01",
    "last_reviewed_date": "2025-06-01",
    "content_version": "1",
}
REVIEW = {
    "review_id": "rev_1",
    "knowledge_id": "know_1",
    "reviewer_role": "OB/GYN Reviewer (Synthetic)",
    "review_date": "2025-06-01",
    "review_status": "APPROVED",
}


def test_validate_topic_valid():
    assert validate_topic(TOPIC) == (True, None)


def test_validate_topic_missing_field():
    ok, reason = validate_topic({**TOPIC, "topic_name": ""})
    assert not ok
    assert "topic_name" in reason


def test_validate_source_valid():
    assert validate_source(SOURCE_ACTIVE) == (True, None)


def test_validate_source_bad_status():
    ok, reason = validate_source({**SOURCE_ACTIVE, "source_status": "DEPRECATED"})
    assert not ok
    assert "source_status" in reason


def test_validate_source_non_https_url():
    ok, reason = validate_source({**SOURCE_ACTIVE, "url": "http://example.gov/a"})
    assert not ok
    assert "https" in reason


def test_validate_knowledge_valid():
    topics_by_id = {"pcos": TOPIC}
    sources_by_id = {"src_a": SOURCE_ACTIVE}
    assert validate_knowledge(KNOWLEDGE, topics_by_id, sources_by_id) == (True, None)


def test_validate_knowledge_unknown_topic():
    ok, reason = validate_knowledge(KNOWLEDGE, topics_by_id={}, sources_by_id={"src_a": SOURCE_ACTIVE})
    assert not ok
    assert "topic_id" in reason


def test_validate_knowledge_unknown_source():
    ok, reason = validate_knowledge(KNOWLEDGE, topics_by_id={"pcos": TOPIC}, sources_by_id={})
    assert not ok
    assert "source_id" in reason


def test_validate_knowledge_bad_review_status():
    row = {**KNOWLEDGE, "review_status": "MAYBE"}
    ok, reason = validate_knowledge(row, {"pcos": TOPIC}, {"src_a": SOURCE_ACTIVE})
    assert not ok
    assert "review_status" in reason


def test_validate_knowledge_accepts_native_date_objects():
    # ReadFromBigQuery hands DATE columns back as datetime.date, not strings - regression guard.
    row = {**KNOWLEDGE, "published_date": date(2025, 1, 1), "last_reviewed_date": date(2025, 6, 1)}
    assert validate_knowledge(row, {"pcos": TOPIC}, {"src_a": SOURCE_ACTIVE}) == (True, None)


def test_validate_knowledge_bad_date():
    row = {**KNOWLEDGE, "published_date": "not-a-date"}
    ok, reason = validate_knowledge(row, {"pcos": TOPIC}, {"src_a": SOURCE_ACTIVE})
    assert not ok
    assert "published_date" in reason


def test_validate_review_valid():
    assert validate_review(REVIEW, knowledge_by_id={"know_1": KNOWLEDGE}) == (True, None)


def test_validate_review_unknown_knowledge_id():
    ok, reason = validate_review(REVIEW, knowledge_by_id={})
    assert not ok
    assert "knowledge_id" in reason


def test_compute_ai_eligible_all_pass():
    assert compute_ai_eligible("APPROVED", "ACTIVE", "CURRENT") is True


def test_compute_ai_eligible_needs_review_fails():
    assert compute_ai_eligible("NEEDS_REVIEW", "ACTIVE", "CURRENT") is False


def test_compute_ai_eligible_inactive_source_fails():
    assert compute_ai_eligible("APPROVED", "INACTIVE", "CURRENT") is False


def test_compute_ai_eligible_stale_content_fails():
    assert compute_ai_eligible("APPROVED", "ACTIVE", "STALE") is False


def test_enrich_knowledge_eligible():
    enriched = enrich_knowledge(KNOWLEDGE, {"pcos": TOPIC}, {"src_a": SOURCE_ACTIVE})
    assert enriched["ai_eligible"] is True
    assert enriched["topic_name"] == "PCOS"
    assert enriched["source_name"] == "Source A"
    assert enriched["content_version"] == 1


def test_enrich_knowledge_ineligible_due_to_inactive_source():
    enriched = enrich_knowledge(KNOWLEDGE, {"pcos": TOPIC}, {"src_a": SOURCE_INACTIVE})
    assert enriched["ai_eligible"] is False


def test_check_duplicates_single_row_passes():
    row, reason = check_duplicates([KNOWLEDGE])
    assert row == KNOWLEDGE
    assert reason is None


def test_check_duplicates_multiple_rows_quarantined():
    row, reason = check_duplicates([KNOWLEDGE, KNOWLEDGE])
    assert row is None
    assert "duplicate" in reason
    assert "2" in reason
