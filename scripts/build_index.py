"""Embed semantic.agent_eligible_knowledge and write semantic.knowledge_embeddings.

    python scripts/build_index.py --project shifahealthai

This is the "indexing pipeline" from docs/rag-design.md: agent_eligible_knowledge -> text
cleaning -> chunking -> Vertex AI embeddings -> vector store. Chunking is a no-op here: our
summaries are short, single-paragraph educational blurbs, so each knowledge record is already
one chunk (chunk_id == knowledge_id). A real corpus of longer source documents would need actual
sliding-window chunking; revisit this the day summaries stop being one paragraph.

The vector store IS BigQuery (semantic.knowledge_embeddings, an ARRAY<FLOAT64> column) rather than
Vertex AI Vector Search / Matching Engine. At 33 rows, standing up a separate managed vector
service would be pure cost with no benefit - brute-force cosine similarity over 33 vectors is
microseconds. BigQuery also keeps this consistent with "BigQuery is authoritative": the vector
data lives next to the governance data it's derived from, not in a second system that could drift.
Revisit if the corpus ever grows enough that brute-force scanning becomes the bottleneck.

Re-run after any batch pipeline run that changes agent_eligible_knowledge - this script always
re-embeds everything (WRITE_TRUNCATE), so it's safe to re-run and always reflects current state.
"""

from __future__ import annotations

import argparse
import sys
from datetime import datetime, timezone

from google import genai
from google.cloud import bigquery

EMBEDDING_MODEL = "text-embedding-005"


def fetch_eligible_knowledge(client: bigquery.Client, project: str) -> list[dict]:
    query = f"SELECT knowledge_id, topic_id, title, summary FROM `{project}.semantic.agent_eligible_knowledge`"
    return [dict(row) for row in client.query(query).result()]


def embed_summaries(genai_client: genai.Client, rows: list[dict]) -> list[list[float]]:
    if not rows:
        return []
    response = genai_client.models.embed_content(
        model=EMBEDDING_MODEL, contents=[row["summary"] for row in rows]
    )
    return [embedding.values for embedding in response.embeddings]


def build_index(project: str, region: str) -> int:
    bq = bigquery.Client(project=project)
    genai_client = genai.Client(vertexai=True, project=project, location=region)

    rows = fetch_eligible_knowledge(bq, project)
    if not rows:
        print("No agent_eligible_knowledge rows found - nothing to embed. Run the batch pipeline first.")
        return 1

    embeddings = embed_summaries(genai_client, rows)
    embedded_at = datetime.now(timezone.utc).isoformat()

    output_rows = [
        {
            "knowledge_id": row["knowledge_id"],
            "topic_id": row["topic_id"],
            "title": row["title"],
            "summary": row["summary"],
            "embedding": embedding,
            "embedding_model": EMBEDDING_MODEL,
            "embedded_at": embedded_at,
        }
        for row, embedding in zip(rows, embeddings)
    ]

    table_ref = f"{project}.semantic.knowledge_embeddings"
    table = bq.get_table(table_ref)
    job_config = bigquery.LoadJobConfig(
        schema=table.schema,
        write_disposition=bigquery.WriteDisposition.WRITE_TRUNCATE,
        source_format=bigquery.SourceFormat.NEWLINE_DELIMITED_JSON,
    )
    job = bq.load_table_from_json(output_rows, table_ref, job_config=job_config)
    job.result()
    print(f"Embedded and loaded {len(output_rows)} rows into {table_ref} using {EMBEDDING_MODEL}")
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--project", default="shifahealthai")
    parser.add_argument("--region", default="us-central1")
    args = parser.parse_args()
    return build_index(args.project, args.region)


if __name__ == "__main__":
    sys.exit(main())
