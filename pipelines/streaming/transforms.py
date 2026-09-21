"""Pure validation logic for interaction events — no Apache Beam import, same split as
pipelines/batch/transforms.py and for the same reason: every rule is unit-testable with plain
dicts, no Pub/Sub, no BigQuery, no Beam runner needed.
"""

from __future__ import annotations

from datetime import datetime

REQUIRED_EVENT_FIELDS = ["event_id", "event_type", "session_id", "occurred_at"]

VALID_EVENT_TYPES = {
    "QUESTION_ASKED",
    "RESPONSE_GENERATED",
    "SOURCE_OPENED",
    "RELATED_TOPIC_OPENED",
    "FEEDBACK_SUBMITTED",
}
VALID_RATINGS = {"up", "down"}

# The full set of columns curated.fact_user_question expects (see
# infra/terraform/modules/bigquery/schemas/curated_fact_user_question.json) - normalize_event()
# fills in any missing ones with None so every row written has a consistent shape.
OUTPUT_FIELDS = [
    "event_id",
    "event_type",
    "session_id",
    "trace_id",
    "topic_id",
    "knowledge_id",
    "rating",
    "latency_ms",
    "source_count",
    "occurred_at",
]


def _missing_fields(event: dict, required: list[str]) -> list[str]:
    return [f for f in required if not str(event.get(f, "")).strip()]


def _parse_timestamp(value) -> datetime | None:
    if isinstance(value, datetime):
        return value
    try:
        return datetime.fromisoformat(str(value))
    except (TypeError, ValueError):
        return None


def validate_event(event: dict) -> tuple[bool, str | None]:
    missing = _missing_fields(event, REQUIRED_EVENT_FIELDS)
    if missing:
        return False, f"missing required fields: {missing}"
    if event["event_type"] not in VALID_EVENT_TYPES:
        return False, f"invalid event_type '{event['event_type']}'"
    rating = event.get("rating")
    if rating is not None and rating not in VALID_RATINGS:
        return False, f"invalid rating '{rating}'"
    if _parse_timestamp(event["occurred_at"]) is None:
        return False, f"unparseable occurred_at '{event['occurred_at']}'"
    return True, None


def normalize_event(event: dict) -> dict:
    """Only call on rows that already passed validate_event. Ensures every row written to
    curated.fact_user_question has exactly OUTPUT_FIELDS, nothing more (defense against an
    unexpected extra field like a stray question_text leaking into the warehouse) and nothing
    less (missing optional fields become None, not absent keys)."""
    return {field: event.get(field) for field in OUTPUT_FIELDS}
