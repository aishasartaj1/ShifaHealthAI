"""Validate data/seed/*.csv + safety_rules.json before they're loaded into BigQuery.

Deliberately stdlib-only (csv, json, datetime) — this is a small pre-load gate, not worth a
dependency. Run directly (`python scripts/validate_seed_data.py`) or via the test in
`scripts/test_validate_seed_data.py`.

Checks referential integrity and enum validity that a plain CSV can't enforce on its own:
topic_id/source_id foreign keys, review_status/content_status/source_status enums, ID
uniqueness, and parseable dates. This is intentionally NOT where ai_eligible gets computed —
that's the Dataflow transform's job in Phase 3 — but it does report a preview count so an
obviously-wrong seed set (e.g. everything stale) is caught before it reaches BigQuery.
"""

from __future__ import annotations

import csv
import json
import sys
from dataclasses import dataclass, field
from datetime import date
from pathlib import Path

SEED_DIR = Path(__file__).resolve().parent.parent / "data" / "seed"

VALID_REVIEW_STATUS = {"APPROVED", "NEEDS_REVIEW", "EXPIRED"}
VALID_CONTENT_STATUS = {"CURRENT", "STALE"}
VALID_SOURCE_STATUS = {"ACTIVE", "INACTIVE"}


@dataclass
class ValidationResult:
    errors: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)

    @property
    def ok(self) -> bool:
        return not self.errors


def _read_csv(path: Path) -> list[dict[str, str]]:
    with path.open(newline="", encoding="utf-8") as f:
        return list(csv.DictReader(f))


def _parse_date(value: str) -> date | None:
    try:
        return date.fromisoformat(value)
    except ValueError:
        return None


def validate_all(seed_dir: Path = SEED_DIR) -> ValidationResult:
    result = ValidationResult()

    topics = _read_csv(seed_dir / "health_topics.csv")
    sources = _read_csv(seed_dir / "sources.csv")
    knowledge = _read_csv(seed_dir / "knowledge_metadata.csv")
    reviews = _read_csv(seed_dir / "medical_reviews.csv")

    topic_ids = {row["topic_id"] for row in topics}
    source_ids = {row["source_id"] for row in sources}
    knowledge_ids = {row["knowledge_id"] for row in knowledge}

    # Uniqueness
    for label, rows, key in [
        ("health_topics", topics, "topic_id"),
        ("sources", sources, "source_id"),
        ("knowledge_metadata", knowledge, "knowledge_id"),
        ("medical_reviews", reviews, "review_id"),
    ]:
        seen = set()
        for row in rows:
            value = row[key]
            if value in seen:
                result.errors.append(f"{label}: duplicate {key} '{value}'")
            seen.add(value)

    # sources.csv enum + url sanity
    for row in sources:
        if row["source_status"] not in VALID_SOURCE_STATUS:
            result.errors.append(
                f"sources[{row['source_id']}]: invalid source_status '{row['source_status']}'"
            )
        if not row["url"].startswith("https://"):
            result.errors.append(f"sources[{row['source_id']}]: url is not https '{row['url']}'")

    # knowledge_metadata.csv: enums, foreign keys, dates
    eligible_count = 0
    for row in knowledge:
        kid = row["knowledge_id"]
        if row["topic_id"] not in topic_ids:
            result.errors.append(f"knowledge_metadata[{kid}]: unknown topic_id '{row['topic_id']}'")
        source_row = next((s for s in sources if s["source_id"] == row["source_id"]), None)
        if source_row is None:
            result.errors.append(f"knowledge_metadata[{kid}]: unknown source_id '{row['source_id']}'")
        if row["review_status"] not in VALID_REVIEW_STATUS:
            result.errors.append(
                f"knowledge_metadata[{kid}]: invalid review_status '{row['review_status']}'"
            )
        if row["content_status"] not in VALID_CONTENT_STATUS:
            result.errors.append(
                f"knowledge_metadata[{kid}]: invalid content_status '{row['content_status']}'"
            )
        for date_field in ("published_date", "last_reviewed_date"):
            if _parse_date(row[date_field]) is None:
                result.errors.append(f"knowledge_metadata[{kid}]: unparseable {date_field} '{row[date_field]}'")
        if not row["summary"].strip():
            result.errors.append(f"knowledge_metadata[{kid}]: empty summary")

        if (
            source_row is not None
            and row["review_status"] == "APPROVED"
            and source_row["source_status"] == "ACTIVE"
            and row["content_status"] == "CURRENT"
        ):
            eligible_count += 1

    # medical_reviews.csv: foreign keys + enum
    for row in reviews:
        if row["knowledge_id"] not in knowledge_ids:
            result.errors.append(
                f"medical_reviews[{row['review_id']}]: unknown knowledge_id '{row['knowledge_id']}'"
            )
        if row["review_status"] not in VALID_REVIEW_STATUS:
            result.errors.append(
                f"medical_reviews[{row['review_id']}]: invalid review_status '{row['review_status']}'"
            )

    if len(knowledge) < 30 or len(knowledge) > 50:
        result.warnings.append(
            f"knowledge_metadata has {len(knowledge)} records; plan targets 30-50 for the MVP"
        )

    result.warnings.append(
        f"ai_eligible preview: {eligible_count}/{len(knowledge)} records would currently be "
        "eligible (this is a preview only — the real flag is computed by the Phase 3 Dataflow job)"
    )

    safety_rules_path = seed_dir / "safety_rules.json"
    try:
        json.loads(safety_rules_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        result.errors.append(f"safety_rules.json: failed to load ({exc})")

    return result


def main() -> int:
    result = validate_all()
    for warning in result.warnings:
        print(f"WARNING: {warning}")
    for error in result.errors:
        print(f"ERROR: {error}")
    if result.ok:
        print("Seed data OK.")
        return 0
    print(f"{len(result.errors)} error(s) found.")
    return 1


if __name__ == "__main__":
    sys.exit(main())
