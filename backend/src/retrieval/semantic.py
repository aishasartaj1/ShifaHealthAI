"""Semantic (embedding-similarity) retrieval.

Cosine similarity is pure Python (no numpy) - at ~33 corpus rows and one query vector this is
microseconds either way, and it keeps this module dependency-light. embed_query/fetch_corpus are
the only IO; rank_by_similarity is what's actually unit-tested.
"""

from __future__ import annotations
import math

from google import genai
from google.cloud import bigquery

EMBEDDING_MODEL = "text-embedding-005"


def cosine_similarity(a: list[float], b: list[float]) -> float:
    dot = sum(x * y for x, y in zip(a, b))
    norm_a = math.sqrt(sum(x * x for x in a))
    norm_b = math.sqrt(sum(x * x for x in b))
    if norm_a == 0 or norm_b == 0:
        return 0.0
    return dot / (norm_a * norm_b)


def rank_by_similarity(query_embedding: list[float], corpus: list[dict]) -> list[dict]:
    """corpus: rows with `embedding` (list[float]) plus whatever metadata to carry through.
    Returns corpus rows (minus the raw `embedding` vector, plus `score`), sorted desc."""
    scored = [
        {**{k: v for k, v in row.items() if k != "embedding"}, "score": cosine_similarity(query_embedding, row["embedding"])}
        for row in corpus
    ]
    return sorted(scored, key=lambda r: r["score"], reverse=True)


def embed_query(client: genai.Client, query: str) -> list[float]:
    response = client.models.embed_content(model=EMBEDDING_MODEL, contents=[query])
    return response.embeddings[0].values


def fetch_embedding_corpus(client: bigquery.Client, project: str, topic: str | None = None) -> list[dict]:
    query = f"SELECT knowledge_id, topic_id, title, summary, embedding FROM `{project}.semantic.knowledge_embeddings`"
    job_config = None
    if topic:
        query += " WHERE topic_id = @topic"
        job_config = bigquery.QueryJobConfig(query_parameters=[bigquery.ScalarQueryParameter("topic", "STRING", topic)])
    return [dict(row) for row in client.query(query, job_config=job_config).result()]


def semantic_search(
    genai_client: genai.Client,
    bq_client: bigquery.Client,
    project: str,
    query: str,
    top_n: int = 10,
    topic: str | None = None,
) -> list[dict]:
    corpus = fetch_embedding_corpus(bq_client, project, topic=topic)
    query_embedding = embed_query(genai_client, query)
    return rank_by_similarity(query_embedding, corpus)[:top_n]
