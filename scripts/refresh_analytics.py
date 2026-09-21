"""Aggregate curated.fact_user_question into semantic.question_analytics.

    python scripts/refresh_analytics.py --project shifahealthai

Same pattern as scripts/build_index.py: a small, explicit, re-runnable script using the plain
BigQuery client, not a Beam job. A true streaming-windowed aggregation (Beam, triggers, continuous
output) was considered and rejected for this event volume - see docs/DEVLOG.md's Phase 7 entry.
This script re-derives semantic.question_analytics from scratch every run (WRITE_TRUNCATE), so
it's safe to re-run after any batch of new events lands via pipelines/streaming/.
"""

from __future__ import annotations

import argparse
import sys
from datetime import datetime, timezone

from google.cloud import bigquery

QUERY_GLOBAL = """
SELECT
  COUNTIF(event_type = 'QUESTION_ASKED') AS total_questions_asked,
  COUNTIF(event_type = 'RESPONSE_GENERATED') AS total_responses_generated,
  AVG(IF(event_type = 'RESPONSE_GENERATED', latency_ms, NULL)) AS avg_response_latency_ms,
  COUNTIF(event_type = 'SOURCE_OPENED') AS total_source_opens,
  COUNTIF(event_type = 'RELATED_TOPIC_OPENED') AS total_related_topic_opens,
  COUNTIF(event_type = 'FEEDBACK_SUBMITTED' AND rating = 'up') AS feedback_up_count,
  COUNTIF(event_type = 'FEEDBACK_SUBMITTED' AND rating = 'down') AS feedback_down_count
FROM `{project}.curated.fact_user_question`
"""

QUERY_BY_TOPIC = """
SELECT
  topic_id,
  COUNTIF(event_type = 'SOURCE_OPENED') AS source_open_count,
  COUNTIF(event_type = 'RELATED_TOPIC_OPENED') AS related_topic_open_count
FROM `{project}.curated.fact_user_question`
WHERE topic_id IS NOT NULL
GROUP BY topic_id
"""


def refresh_analytics(project: str) -> int:
    client = bigquery.Client(project=project)
    computed_at = datetime.now(timezone.utc).isoformat()

    global_row = list(client.query(QUERY_GLOBAL.format(project=project)).result())[0]
    rows = [
        {"metric_name": name, "dimension": None, "metric_value": float(value or 0), "computed_at": computed_at}
        for name, value in dict(global_row).items()
    ]

    for topic_row in client.query(QUERY_BY_TOPIC.format(project=project)).result():
        topic_row = dict(topic_row)
        topic_id = topic_row.pop("topic_id")
        for metric_name, value in topic_row.items():
            rows.append(
                {
                    "metric_name": metric_name,
                    "dimension": topic_id,
                    "metric_value": float(value or 0),
                    "computed_at": computed_at,
                }
            )

    table_ref = f"{project}.semantic.question_analytics"
    table = client.get_table(table_ref)
    job_config = bigquery.LoadJobConfig(
        schema=table.schema,
        write_disposition=bigquery.WriteDisposition.WRITE_TRUNCATE,
        source_format=bigquery.SourceFormat.NEWLINE_DELIMITED_JSON,
    )
    job = client.load_table_from_json(rows, table_ref, job_config=job_config)
    job.result()
    print(f"Loaded {len(rows)} metric rows into {table_ref}")
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--project", default="shifahealthai")
    args = parser.parse_args()
    return refresh_analytics(args.project)


if __name__ == "__main__":
    sys.exit(main())
