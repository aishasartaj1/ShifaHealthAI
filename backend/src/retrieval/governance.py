"""Query-time governance re-check — the actual enforcement of "govern before generation".

The vector index (semantic.knowledge_embeddings) is a snapshot from whenever scripts/build_index.py
last ran. Between that run and any given query, a record's eligibility can change: a review can
expire, a source can go inactive, content can go stale. filter_eligible() is what catches that
drift by re-checking against BigQuery's CURRENT state at query time, not trusting the index's
snapshot as final truth (see docs/governance.md "Enforcement points", #3).
"""

from __future__ import annotations

from google.cloud import bigquery


def filter_eligible(candidates: list[dict], eligible_ids: set[str]) -> list[dict]:
    """Pure: drop any candidate whose knowledge_id isn't currently eligible. Preserves order
    (candidates are already ranked by the caller) and doesn't care how eligible_ids was fetched."""
    return [c for c in candidates if c["knowledge_id"] in eligible_ids]


def fetch_currently_eligible_ids(client: bigquery.Client, project: str) -> set[str]:
    """IO: the live governance check. Queries semantic.agent_eligible_knowledge fresh - this is
    exactly the table the Phase 3 batch pipeline computes ai_eligible into - rather than reusing
    whatever was true when the index was built."""
    query = f"SELECT knowledge_id FROM `{project}.semantic.agent_eligible_knowledge`"
    return {row["knowledge_id"] for row in client.query(query).result()}
