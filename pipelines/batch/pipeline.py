"""Beam pipeline: raw.* -> validate/dedup -> curated.* + semantic.* (valid rows), quarantine (invalid).

All business logic lives in transforms.py (framework-free, unit-tested). This file is just the
DAG wiring: dedup each raw table, validate it (with FK checks against side inputs from tables
already validated earlier in the chain), write valid rows to curated/semantic, and merge every
rejected row — duplicates and validation failures alike — into one quarantine sink.

Dependency order matters here and mirrors the FK structure: topics/sources have no dependencies,
so they're validated first; knowledge depends on both (topic_id, source_id); reviews depend on
knowledge (knowledge_id). Each stage's side input is built only from the PRIOR stage's valid
output, not the raw input — a knowledge record referencing a topic that itself failed validation
is correctly treated as unresolvable, not as a fluke.
"""

from __future__ import annotations

import json
from datetime import date, datetime, timezone


def _json_default(value):
    """Quarantined rows carry whatever BigQuery gave us, including `datetime.date` for DATE
    columns - json.dumps doesn't know how to serialize those on its own."""
    if isinstance(value, date):
        return value.isoformat()
    raise TypeError(f"Object of type {type(value).__name__} is not JSON serializable")

import apache_beam as beam
from apache_beam.io import ReadFromBigQuery, WriteToBigQuery, WriteToText
from apache_beam.io.gcp.bigquery import BigQueryDisposition
from apache_beam.options.pipeline_options import PipelineOptions
from google.cloud import bigquery as bq_client_lib

import transforms

_OUTPUT_TABLES = [
    "curated.dim_health_topic",
    "curated.dim_source",
    "curated.dim_knowledge",
    "curated.fact_medical_review",
    "semantic.knowledge_catalog",
    "semantic.approved_knowledge",
    "semantic.agent_eligible_knowledge",
    "semantic.topic_knowledge_summary",
]


def _truncate_output_tables(project: str) -> None:
    """STREAMING_INSERTS can't use WRITE_TRUNCATE (BigQuery limitation), so this batch job
    truncates its own output tables up front and streams with WRITE_APPEND instead - same
    full-refresh-per-run behavior, just split into two steps instead of one disposition flag."""
    client = bq_client_lib.Client(project=project)
    for table in _OUTPUT_TABLES:
        client.query(f"TRUNCATE TABLE `{project}.{table}`").result()


def _read(pipeline, project: str, dataset: str, table: str, label: str):
    return pipeline | f"Read_{label}" >> ReadFromBigQuery(
        query=f"SELECT * FROM `{project}.{dataset}.{table}`",
        use_standard_sql=True,
        method=ReadFromBigQuery.Method.DIRECT_READ,
    )


class DedupFn(beam.DoFn):
    """Input: (id, [row, row, ...]) grouped by id. Splits into unique-row / duplicate-rows."""

    def process(self, element):
        _key, rows = element
        rows = list(rows)
        row, reason = transforms.check_duplicates(rows)
        if row is not None:
            yield row
        else:
            for r in rows:
                yield beam.pvalue.TaggedOutput("duplicate", (r, reason))


def dedup(pcoll, id_field: str, label: str):
    tagged = (
        pcoll
        | f"KeyById_{label}" >> beam.Map(lambda r, f=id_field: (r[f], r))
        | f"GroupById_{label}" >> beam.GroupByKey()
        | f"Dedup_{label}" >> beam.ParDo(DedupFn()).with_outputs("duplicate", main="unique")
    )
    return tagged.unique, tagged.duplicate


class ValidateFn(beam.DoFn):
    def __init__(self, validate_fn):
        self._validate_fn = validate_fn

    def process(self, element, **side_inputs):
        ok, reason = self._validate_fn(element, **side_inputs)
        if ok:
            yield element
        else:
            yield beam.pvalue.TaggedOutput("invalid", (element, reason))


def validate(pcoll, validate_fn, label: str, **side_inputs):
    tagged = pcoll | f"Validate_{label}" >> beam.ParDo(
        ValidateFn(validate_fn), **side_inputs
    ).with_outputs("invalid", main="valid")
    return tagged.valid, tagged.invalid


def _as_dict_by(pcoll, key_field: str, label: str):
    return beam.pvalue.AsDict(pcoll | f"KeyValueFor_{label}" >> beam.Map(lambda r, f=key_field: (r[f], r)))


def _tag_quarantine(table_name: str):
    def _tag(element):
        row, reason = element
        return {"table": table_name, "reason": reason, "row": row}

    return _tag


def run(
    project: str,
    quarantine_bucket: str,
    run_id: str | None = None,
    pipeline_args: list[str] | None = None,
) -> None:
    run_id = run_id or datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    options = PipelineOptions(pipeline_args or [])

    _truncate_output_tables(project)

    with beam.Pipeline(options=options) as p:
        raw_topics = _read(p, project, "raw", "raw_topics", "topics")
        raw_sources = _read(p, project, "raw", "raw_sources", "sources")
        raw_knowledge = _read(p, project, "raw", "raw_knowledge", "knowledge")
        raw_reviews = _read(p, project, "raw", "raw_reviews", "reviews")

        topics_unique, topics_dup = dedup(raw_topics, "topic_id", "topics")
        sources_unique, sources_dup = dedup(raw_sources, "source_id", "sources")
        knowledge_unique, knowledge_dup = dedup(raw_knowledge, "knowledge_id", "knowledge")
        reviews_unique, reviews_dup = dedup(raw_reviews, "review_id", "reviews")

        valid_topics, invalid_topics = validate(topics_unique, transforms.validate_topic, "topics")
        valid_sources, invalid_sources = validate(sources_unique, transforms.validate_source, "sources")

        topics_by_id = _as_dict_by(valid_topics, "topic_id", "topics")
        sources_by_id = _as_dict_by(valid_sources, "source_id", "sources")

        valid_knowledge_raw, invalid_knowledge = validate(
            knowledge_unique,
            transforms.validate_knowledge,
            "knowledge",
            topics_by_id=topics_by_id,
            sources_by_id=sources_by_id,
        )
        enriched_knowledge = valid_knowledge_raw | "EnrichKnowledge" >> beam.Map(
            transforms.enrich_knowledge, topics_by_id=topics_by_id, sources_by_id=sources_by_id
        )

        knowledge_by_id = _as_dict_by(enriched_knowledge, "knowledge_id", "knowledge")
        valid_reviews, invalid_reviews = validate(
            reviews_unique, transforms.validate_review, "reviews", knowledge_by_id=knowledge_by_id
        )

        # --- curated layer ---
        write_kwargs = dict(
            create_disposition=BigQueryDisposition.CREATE_NEVER,
            write_disposition=BigQueryDisposition.WRITE_APPEND,  # tables truncated up front, see _truncate_output_tables
            method=WriteToBigQuery.Method.STREAMING_INSERTS,
        )
        valid_topics | "WriteDimTopic" >> WriteToBigQuery(
            table=f"{project}:curated.dim_health_topic", **write_kwargs
        )
        valid_sources | "WriteDimSource" >> WriteToBigQuery(table=f"{project}:curated.dim_source", **write_kwargs)
        enriched_knowledge | "MapDimKnowledge" >> beam.Map(
            lambda r: {k: r[k] for k in transforms.REQUIRED_KNOWLEDGE_FIELDS + ["ai_eligible"]}
        ) | "WriteDimKnowledge" >> WriteToBigQuery(table=f"{project}:curated.dim_knowledge", **write_kwargs)
        valid_reviews | "WriteFactReview" >> WriteToBigQuery(
            table=f"{project}:curated.fact_medical_review", **write_kwargs
        )

        # --- semantic layer ---
        catalog_fields = [
            "knowledge_id",
            "topic_id",
            "topic_name",
            "source_id",
            "source_name",
            "title",
            "summary",
            "review_status",
            "content_status",
            "ai_eligible",
            "published_date",
            "last_reviewed_date",
            "content_version",
        ]
        catalog = enriched_knowledge | "MapCatalog" >> beam.Map(lambda r, fs=catalog_fields: {k: r[k] for k in fs})
        catalog | "WriteKnowledgeCatalog" >> WriteToBigQuery(
            table=f"{project}:semantic.knowledge_catalog", **write_kwargs
        )
        catalog | "FilterApproved" >> beam.Filter(
            lambda r: r["review_status"] == "APPROVED"
        ) | "WriteApprovedKnowledge" >> WriteToBigQuery(
            table=f"{project}:semantic.approved_knowledge", **write_kwargs
        )
        catalog | "FilterEligible" >> beam.Filter(lambda r: r["ai_eligible"]) | "MapEligible" >> beam.Map(
            lambda r: {k: r[k] for k in ["knowledge_id", "topic_id", "title", "summary"]}
        ) | "WriteAgentEligible" >> WriteToBigQuery(
            table=f"{project}:semantic.agent_eligible_knowledge", **write_kwargs
        )

        (
            catalog
            | "KeyByTopicForSummary" >> beam.Map(lambda r: (r["topic_id"], r))
            | "GroupByTopicForSummary" >> beam.GroupByKey()
            | "SummarizeTopic"
            >> beam.Map(
                lambda kv: {
                    "topic_id": kv[0],
                    "topic_name": next(iter(kv[1]))["topic_name"],
                    "total_count": len(list(kv[1])),
                    "eligible_count": sum(1 for r in kv[1] if r["ai_eligible"]),
                    "approved_count": sum(1 for r in kv[1] if r["review_status"] == "APPROVED"),
                    "needs_review_count": sum(1 for r in kv[1] if r["review_status"] == "NEEDS_REVIEW"),
                    "expired_count": sum(1 for r in kv[1] if r["review_status"] == "EXPIRED"),
                    "stale_count": sum(1 for r in kv[1] if r["content_status"] == "STALE"),
                }
            )
            | "WriteTopicSummary" >> WriteToBigQuery(table=f"{project}:semantic.topic_knowledge_summary", **write_kwargs)
        )

        # --- quarantine: every rejected row, from any stage, any table ---
        quarantined = (
            (
                topics_dup | "TagDupTopics" >> beam.Map(_tag_quarantine("raw_topics")),
                sources_dup | "TagDupSources" >> beam.Map(_tag_quarantine("raw_sources")),
                knowledge_dup | "TagDupKnowledge" >> beam.Map(_tag_quarantine("raw_knowledge")),
                reviews_dup | "TagDupReviews" >> beam.Map(_tag_quarantine("raw_reviews")),
                invalid_topics | "TagInvalidTopics" >> beam.Map(_tag_quarantine("raw_topics")),
                invalid_sources | "TagInvalidSources" >> beam.Map(_tag_quarantine("raw_sources")),
                invalid_knowledge | "TagInvalidKnowledge" >> beam.Map(_tag_quarantine("raw_knowledge")),
                invalid_reviews | "TagInvalidReviews" >> beam.Map(_tag_quarantine("raw_reviews")),
            )
            | "FlattenQuarantine" >> beam.Flatten()
        )
        (
            quarantined
            | "SerializeQuarantine" >> beam.Map(lambda r: json.dumps(r, default=_json_default))
            | "WriteQuarantine" >> WriteToText(f"gs://{quarantine_bucket}/{run_id}/quarantine", file_name_suffix=".jsonl")
        )
