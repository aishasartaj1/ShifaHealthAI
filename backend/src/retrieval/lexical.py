"""Lexical (BM25 keyword) retrieval — precision for exact terms hybrid semantic search can miss:
named conditions, acronyms (PCOS, HPV, IUD), exact test names.
"""

from __future__ import annotations

from google.cloud import bigquery
from rank_bm25 import BM25Okapi


def _tokenize(text: str) -> list[str]:
    return text.lower().split()


def rank_by_bm25(query: str, corpus: list[dict]) -> list[dict]:
    """corpus: rows with `title` + `summary` (+ whatever metadata to carry through).
    Returns corpus rows plus `score`, sorted desc. Pure/offline - no GCP calls, just rank_bm25
    over whatever corpus is handed in."""
    if not corpus:
        return []
    tokenized_corpus = [_tokenize(f"{row['title']} {row['summary']}") for row in corpus]
    bm25 = BM25Okapi(tokenized_corpus)
    scores = bm25.get_scores(_tokenize(query))
    scored = [{**row, "score": float(score)} for row, score in zip(corpus, scores)]
    return sorted(scored, key=lambda r: r["score"], reverse=True)


def fetch_lexical_corpus(client: bigquery.Client, project: str, topic: str | None = None) -> list[dict]:
    query = f"SELECT knowledge_id, topic_id, title, summary FROM `{project}.semantic.agent_eligible_knowledge`"
    job_config = None
    if topic:
        query += " WHERE topic_id = @topic"
        job_config = bigquery.QueryJobConfig(query_parameters=[bigquery.ScalarQueryParameter("topic", "STRING", topic)])
    return [dict(row) for row in client.query(query, job_config=job_config).result()]


def lexical_search(
    client: bigquery.Client, project: str, query: str, top_n: int = 10, topic: str | None = None
) -> list[dict]:
    corpus = fetch_lexical_corpus(client, project, topic=topic)
    return rank_by_bm25(query, corpus)[:top_n]
