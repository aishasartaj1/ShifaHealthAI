"""Load data/seed/*.csv into the `raw` BigQuery dataset created by infra/terraform/modules/bigquery.

Usage:
    python scripts/seed_bigquery.py [--project shifahealthai]

Refuses to load if validate_seed_data.py finds any errors — a bad seed row should fail loudly
here, not silently land in BigQuery. Uses WRITE_TRUNCATE per table so this script is safe to
re-run after editing the seed CSVs.
"""

from __future__ import annotations

import argparse
import csv
import sys
from pathlib import Path

from google.cloud import bigquery

from validate_seed_data import SEED_DIR, validate_all

# (csv filename, table name, columns that need casting from str -> int)
TABLES = [
    ("health_topics.csv", "raw_topics", []),
    ("sources.csv", "raw_sources", []),
    ("knowledge_metadata.csv", "raw_knowledge", ["content_version"]),
    ("medical_reviews.csv", "raw_reviews", []),
]


def _load_rows(csv_path: Path, int_columns: list[str]) -> list[dict]:
    with csv_path.open(newline="", encoding="utf-8") as f:
        rows = list(csv.DictReader(f))
    for row in rows:
        for column in int_columns:
            row[column] = int(row[column])
    return rows


def seed(project_id: str, dataset: str = "raw") -> None:
    client = bigquery.Client(project=project_id)

    for csv_name, table_name, int_columns in TABLES:
        rows = _load_rows(SEED_DIR / csv_name, int_columns)
        table_ref = f"{project_id}.{dataset}.{table_name}"
        table = client.get_table(table_ref)

        job_config = bigquery.LoadJobConfig(
            schema=table.schema,
            write_disposition=bigquery.WriteDisposition.WRITE_TRUNCATE,
            source_format=bigquery.SourceFormat.NEWLINE_DELIMITED_JSON,
        )
        job = client.load_table_from_json(rows, table_ref, job_config=job_config)
        job.result()
        print(f"Loaded {len(rows)} rows into {table_ref}")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--project", default="shifahealthai")
    args = parser.parse_args()

    validation = validate_all()
    for warning in validation.warnings:
        print(f"WARNING: {warning}")
    if not validation.ok:
        for error in validation.errors:
            print(f"ERROR: {error}")
        print("Refusing to load: fix the seed data errors above first.")
        return 1

    seed(args.project)
    return 0


if __name__ == "__main__":
    sys.exit(main())
