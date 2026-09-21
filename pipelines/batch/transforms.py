"""Pure validation/enrichment logic for the batch pipeline — no Apache Beam import here on purpose.

Keeping this framework-free means every rule (required fields, enum values, foreign keys,
ai_eligible computation) is unit-testable with plain pytest and plain dicts, with no Beam runner
needed. pipeline.py wires these functions into DoFns; it should not contain business logic itself.
"""

from __future__ import annotations

from datetime import date

REQUIRED_TOPIC_FIELDS = ["topic_id", "topic_name", "parent_category"]
REQUIRED_SOURCE_FIELDS = ["source_id", "source_name", "source_type", "url", "source_status"]
REQUIRED_KNOWLEDGE_FIELDS = [
    "knowledge_id",
    "topic_id",
    "source_id",
    "title",
    "summary",
    "review_status",
    "content_status",
    "published_date",
    "last_reviewed_date",
    "content_version",
]
REQUIRED_REVIEW_FIELDS = ["review_id", "knowledge_id", "reviewer_role", "review_date", "review_status"]

VALID_REVIEW_STATUS = {"APPROVED", "NEEDS_REVIEW", "EXPIRED"}
VALID_CONTENT_STATUS = {"CURRENT", "STALE"}
VALID_SOURCE_STATUS = {"ACTIVE", "INACTIVE"}


def _missing_fields(row: dict, required: list[str]) -> list[str]:
    return [f for f in required if not str(row.get(f, "")).strip()]


def _parse_date(value) -> date | None:
    """Accepts either an ISO date string (CSV/tests) or a native `date` (BigQuery DATE columns
    come back as `datetime.date` via ReadFromBigQuery, not strings)."""
    if isinstance(value, date):
        return value
    try:
        return date.fromisoformat(value)
    except (TypeError, ValueError):
        return None


def validate_topic(row: dict) -> tuple[bool, str | None]:
    missing = _missing_fields(row, REQUIRED_TOPIC_FIELDS)
    if missing:
        return False, f"missing required fields: {missing}"
    return True, None


def validate_source(row: dict) -> tuple[bool, str | None]:
    missing = _missing_fields(row, REQUIRED_SOURCE_FIELDS)
    if missing:
        return False, f"missing required fields: {missing}"
    if row["source_status"] not in VALID_SOURCE_STATUS:
        return False, f"invalid source_status '{row['source_status']}'"
    if not row["url"].startswith("https://"):
        return False, f"url is not https: '{row['url']}'"
    return True, None


def validate_knowledge(row: dict, topics_by_id: dict, sources_by_id: dict) -> tuple[bool, str | None]:
    missing = _missing_fields(row, REQUIRED_KNOWLEDGE_FIELDS)
    if missing:
        return False, f"missing required fields: {missing}"
    if row["topic_id"] not in topics_by_id:
        return False, f"unknown topic_id '{row['topic_id']}'"
    if row["source_id"] not in sources_by_id:
        return False, f"unknown source_id '{row['source_id']}'"
    if row["review_status"] not in VALID_REVIEW_STATUS:
        return False, f"invalid review_status '{row['review_status']}'"
    if row["content_status"] not in VALID_CONTENT_STATUS:
        return False, f"invalid content_status '{row['content_status']}'"
    if _parse_date(row["published_date"]) is None:
        return False, f"unparseable published_date '{row['published_date']}'"
    if _parse_date(row["last_reviewed_date"]) is None:
        return False, f"unparseable last_reviewed_date '{row['last_reviewed_date']}'"
    return True, None


def validate_review(row: dict, knowledge_by_id: dict) -> tuple[bool, str | None]:
    missing = _missing_fields(row, REQUIRED_REVIEW_FIELDS)
    if missing:
        return False, f"missing required fields: {missing}"
    if row["knowledge_id"] not in knowledge_by_id:
        return False, f"unknown knowledge_id '{row['knowledge_id']}'"
    if row["review_status"] not in VALID_REVIEW_STATUS:
        return False, f"invalid review_status '{row['review_status']}'"
    return True, None


def compute_ai_eligible(review_status: str, source_status: str, content_status: str) -> bool:
    """The one governance computation this whole pipeline exists to do.

    Deliberately not stored in raw data (see docs/DEVLOG.md) — this is where it actually gets
    computed, from the three independent governance signals, each owned by a different table.
    """
    return review_status == "APPROVED" and source_status == "ACTIVE" and content_status == "CURRENT"


def enrich_knowledge(row: dict, topics_by_id: dict, sources_by_id: dict) -> dict:
    """Only call on rows that already passed validate_knowledge."""
    topic = topics_by_id[row["topic_id"]]
    source = sources_by_id[row["source_id"]]
    enriched = dict(row)
    enriched["content_version"] = int(row["content_version"])
    enriched["topic_name"] = topic["topic_name"]
    enriched["source_name"] = source["source_name"]
    enriched["ai_eligible"] = compute_ai_eligible(
        row["review_status"], source["source_status"], row["content_status"]
    )
    return enriched


def check_duplicates(rows: list[dict]) -> tuple[dict | None, str | None]:
    """rows: every raw row sharing the same id. One row -> (row, None). More -> (None, reason).

    Deliberately quarantines ALL copies rather than picking a "winner" — there's no safe way to
    know which copy is correct without more information, so this forces a human to fix the
    source data instead of the pipeline silently guessing.
    """
    if len(rows) == 1:
        return rows[0], None
    return None, f"duplicate id: {len(rows)} rows share this identifier"
