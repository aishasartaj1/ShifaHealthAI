"""Structured BigQuery lookups backing the internal API (backend/src/api/internal.py) — the
"Structured SQL tools" box in architecture.md, as opposed to the hybrid RAG in retrieval/.

All queries are parameterized (no string-interpolated user input into SQL) and read only from the
semantic/curated layers, never raw — consistent with "the AI system should not depend directly on
raw ingestion tables" (docs/data-model.md).
"""

from __future__ import annotations

from functools import lru_cache

from google.cloud import bigquery


@lru_cache
def get_bigquery_client() -> bigquery.Client:
    return bigquery.Client()


def get_knowledge_record(client: bigquery.Client, project: str, knowledge_id: str) -> dict | None:
    query = f"SELECT * FROM `{project}.semantic.knowledge_catalog` WHERE knowledge_id = @knowledge_id"
    job_config = bigquery.QueryJobConfig(
        query_parameters=[bigquery.ScalarQueryParameter("knowledge_id", "STRING", knowledge_id)]
    )
    rows = list(client.query(query, job_config=job_config).result())
    return dict(rows[0]) if rows else None


def get_source_record(client: bigquery.Client, project: str, source_id: str) -> dict | None:
    query = f"SELECT * FROM `{project}.curated.dim_source` WHERE source_id = @source_id"
    job_config = bigquery.QueryJobConfig(
        query_parameters=[bigquery.ScalarQueryParameter("source_id", "STRING", source_id)]
    )
    rows = list(client.query(query, job_config=job_config).result())
    return dict(rows[0]) if rows else None


def check_eligibility(client: bigquery.Client, project: str, knowledge_id: str) -> bool | None:
    """None means the knowledge_id doesn't exist at all (distinct from existing-but-ineligible)."""
    query = f"SELECT ai_eligible FROM `{project}.semantic.knowledge_catalog` WHERE knowledge_id = @knowledge_id"
    job_config = bigquery.QueryJobConfig(
        query_parameters=[bigquery.ScalarQueryParameter("knowledge_id", "STRING", knowledge_id)]
    )
    rows = list(client.query(query, job_config=job_config).result())
    return bool(rows[0]["ai_eligible"]) if rows else None


def list_topics(client: bigquery.Client, project: str) -> list[dict]:
    query = f"SELECT topic_id, topic_name, parent_category, description FROM `{project}.curated.dim_health_topic` ORDER BY topic_name"
    return [dict(row) for row in client.query(query).result()]


def list_related_topics(client: bigquery.Client, project: str, topic_id: str, limit: int = 3) -> list[dict]:
    """Simple, explainable heuristic: other topics in the same parent_category (e.g. PCOS ->
    Menopause, both Hormonal Health), falling back to any other topic if the category has no
    siblings. Not similarity-scored - there's no topic-relatedness data to score against yet;
    revisit if that ever gets built (e.g. from co-occurring retrieval results)."""
    same_category_query = f"""
        SELECT topic_id, topic_name, parent_category
        FROM `{project}.curated.dim_health_topic`
        WHERE topic_id != @topic_id
          AND parent_category = (
            SELECT parent_category FROM `{project}.curated.dim_health_topic` WHERE topic_id = @topic_id
          )
        ORDER BY topic_name
        LIMIT @limit
    """
    job_config = bigquery.QueryJobConfig(
        query_parameters=[
            bigquery.ScalarQueryParameter("topic_id", "STRING", topic_id),
            bigquery.ScalarQueryParameter("limit", "INT64", limit),
        ]
    )
    related = [dict(row) for row in client.query(same_category_query, job_config=job_config).result()]
    if related:
        return related

    fallback_query = f"""
        SELECT topic_id, topic_name, parent_category
        FROM `{project}.curated.dim_health_topic`
        WHERE topic_id != @topic_id
        ORDER BY topic_name
        LIMIT @limit
    """
    return [dict(row) for row in client.query(fallback_query, job_config=job_config).result()]
