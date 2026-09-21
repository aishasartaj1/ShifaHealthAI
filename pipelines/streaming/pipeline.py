"""Beam streaming pipeline: Pub/Sub subscription -> validate -> curated.fact_user_question.
Invalid messages -> curated.quarantined_events (a BigQuery table, not a GCS file - see that
table's schema comment for why an unbounded source quarantines differently than batch's does).

All business logic lives in transforms.py (framework-free, unit-tested) - this file is DAG wiring
only, same split as pipelines/batch/. Streaming inserts (not file loads) throughout, since both
output tables are append-only event logs that never need a full-refresh truncate.
"""

from __future__ import annotations

import json
from datetime import date, datetime

import apache_beam as beam
from apache_beam.io import ReadFromPubSub, WriteToBigQuery
from apache_beam.io.gcp.bigquery import BigQueryDisposition
from apache_beam.options.pipeline_options import PipelineOptions, StandardOptions

import transforms


def _json_default(value):
    if isinstance(value, (date, datetime)):
        return value.isoformat()
    raise TypeError(f"Object of type {type(value).__name__} is not JSON serializable")


class ParseAndValidateFn(beam.DoFn):
    def process(self, message_bytes: bytes):
        try:
            event = json.loads(message_bytes.decode("utf-8"))
        except (json.JSONDecodeError, UnicodeDecodeError) as exc:
            yield beam.pvalue.TaggedOutput(
                "invalid", {"reason": f"unparseable JSON: {exc}", "raw_payload": message_bytes.decode("utf-8", errors="replace")}
            )
            return

        ok, reason = transforms.validate_event(event)
        if ok:
            yield transforms.normalize_event(event)
        else:
            yield beam.pvalue.TaggedOutput(
                "invalid", {"reason": reason, "raw_payload": json.dumps(event, default=_json_default)}
            )


def build_pipeline(p: beam.Pipeline, project: str, subscription: str) -> None:
    subscription_path = f"projects/{project}/subscriptions/{subscription}"

    tagged = (
        p
        | "ReadEvents" >> ReadFromPubSub(subscription=subscription_path)
        | "ParseAndValidate" >> beam.ParDo(ParseAndValidateFn()).with_outputs("invalid", main="valid")
    )

    tagged.valid | "WriteFactUserQuestion" >> WriteToBigQuery(
        table=f"{project}:curated.fact_user_question",
        create_disposition=BigQueryDisposition.CREATE_NEVER,
        write_disposition=BigQueryDisposition.WRITE_APPEND,
        method=WriteToBigQuery.Method.STREAMING_INSERTS,
    )

    (
        tagged.invalid
        | "AddQuarantineTimestamp" >> beam.Map(lambda row: {**row, "quarantined_at": datetime.utcnow().isoformat()})
        | "WriteQuarantinedEvents" >> WriteToBigQuery(
            table=f"{project}:curated.quarantined_events",
            create_disposition=BigQueryDisposition.CREATE_NEVER,
            write_disposition=BigQueryDisposition.WRITE_APPEND,
            method=WriteToBigQuery.Method.STREAMING_INSERTS,
        )
    )


def run(project: str, subscription: str, pipeline_args: list[str] | None = None) -> beam.runners.runner.PipelineResult:
    options = PipelineOptions(pipeline_args or [])
    options.view_as(StandardOptions).streaming = True

    pipeline = beam.Pipeline(options=options)
    build_pipeline(pipeline, project, subscription)
    return pipeline.run()
