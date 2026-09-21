"""Structured BigQuery lookups — the "Structured SQL tools" box in architecture.md, as opposed to
the hybrid RAG in retrieval/. Shared by the internal API (backend/src/api/internal.py, the agent's
tools) and the public API (backend/src/api/{topics,knowledge,admin}.py, the frontend) - same
queries, same governance guarantees, different callers and different auth.

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


def list_knowledge_by_topic(client: bigquery.Client, project: str, topic_id: str) -> list[dict]:
    """Backs the topic explorer (frontend Topics.tsx) - not in the plan's original Section 19
    API list, added because a topic explorer that can't show a topic's actual records isn't
    much of an explorer. See docs/DEVLOG.md's Phase 6 entry."""
    query = f"""
        SELECT knowledge_id, title, summary, review_status, content_status, ai_eligible
        FROM `{project}.semantic.knowledge_catalog`
        WHERE topic_id = @topic_id
        ORDER BY title
    """
    job_config = bigquery.QueryJobConfig(
        query_parameters=[bigquery.ScalarQueryParameter("topic_id", "STRING", topic_id)]
    )
    return [dict(row) for row in client.query(query, job_config=job_config).result()]


def get_quality_summary(client: bigquery.Client, project: str) -> dict:
    """Backs GET /api/admin/quality - bundles the plan's Section 25 data-quality metrics and the
    Section 4.2 "quarantined/non-eligible records" governance view in one response, since both
    come from the same underlying data and the plan only specifies one endpoint for this."""
    topic_rows = [
        dict(row)
        for row in client.query(
            f"SELECT * FROM `{project}.semantic.topic_knowledge_summary` ORDER BY topic_name"
        ).result()
    ]
    total = sum(row["total_count"] for row in topic_rows)
    eligible = sum(row["eligible_count"] for row in topic_rows)

    ineligible_query = f"""
        SELECT knowledge_id, topic_id, topic_name, title, review_status, content_status
        FROM `{project}.semantic.knowledge_catalog`
        WHERE ai_eligible = FALSE
        ORDER BY topic_id, knowledge_id
    """
    ineligible_records = [dict(row) for row in client.query(ineligible_query).result()]

    return {
        "total_knowledge_count": total,
        "eligible_count": eligible,
        "eligible_percentage": round(100 * eligible / total, 1) if total else 0.0,
        "by_topic": topic_rows,
        "ineligible_records": ineligible_records,
    }


def get_analytics_summary(client: bigquery.Client, project: str) -> dict:
    """Backs GET /api/admin/analytics. Reads semantic.question_analytics, the key/value metrics
    table scripts/refresh_analytics.py maintains (see its module docstring for why this is a
    periodic-refresh script rather than continuous streaming aggregation) - reshapes the flat
    (metric_name, dimension, metric_value) rows into a global dict + a by-topic breakdown."""
    rows = [
        dict(row)
        for row in client.query(
            f"SELECT metric_name, dimension, metric_value, computed_at FROM `{project}.semantic.question_analytics`"
        ).result()
    ]
    global_metrics: dict[str, float] = {}
    by_topic: dict[str, dict[str, float]] = {}
    computed_at = None

    for row in rows:
        computed_at = row["computed_at"]
        if row["dimension"] is None:
            global_metrics[row["metric_name"]] = row["metric_value"]
        else:
            by_topic.setdefault(row["dimension"], {})[row["metric_name"]] = row["metric_value"]

    return {
        "global": global_metrics,
        "by_topic": [{"topic_id": topic_id, **metrics} for topic_id, metrics in by_topic.items()],
        "computed_at": str(computed_at) if computed_at else None,
    }
