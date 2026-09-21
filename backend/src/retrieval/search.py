"""search_knowledge(): the hybrid RAG entrypoint from docs/rag-design.md Section 11.2 —
semantic + lexical -> merge/dedupe/rerank -> governance filter -> top governed candidates.

This is IO-heavy composition (two BigQuery queries, one embedding call, one more BigQuery
query for the governance check), so it isn't unit tested itself - hybrid.py and governance.py's
pure logic are what's tested. This is what backend/src/api/internal.py's POST /internal/search-knowledge
route calls, which is in turn what the agents/ service's search_knowledge tool calls over HTTP
(see architecture.md's Service Topology: agents/ owns the tool definitions, backend owns the
actual retrieval/BigQuery/Vertex AI code).
"""

from __future__ import annotations

from google import genai
from google.cloud import bigquery

from src.retrieval import governance, hybrid, lexical, semantic


def search_knowledge(
    genai_client: genai.Client,
    bq_client: bigquery.Client,
    project: str,
    query: str,
    top_n: int = 5,
    topic: str | None = None,
    semantic_weight: float = 0.6,
    lexical_weight: float = 0.4,
) -> list[dict]:
    semantic_results = semantic.semantic_search(genai_client, bq_client, project, query, top_n=10, topic=topic)
    lexical_results = lexical.lexical_search(bq_client, project, query, top_n=10, topic=topic)

    # Ask for more than top_n before governance filtering shrinks the list, so a query that
    # happens to surface a couple of now-ineligible candidates doesn't starve the final result.
    merged = hybrid.merge_and_rerank(
        semantic_results, lexical_results, semantic_weight, lexical_weight, top_n=top_n * 2
    )

    eligible_ids = governance.fetch_currently_eligible_ids(bq_client, project)
    governed = governance.filter_eligible(merged, eligible_ids)
    return governed[:top_n]
