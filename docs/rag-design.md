# Hybrid RAG Design

Women's-health questions need both semantic understanding (paraphrases, conceptual similarity) and lexical
precision (named conditions, medications, tests, acronyms, exact terms) — hence hybrid retrieval rather than
semantic-only.

## Indexing pipeline

```
semantic.agent_eligible_knowledge -> text cleaning -> chunking -> Vertex AI text embeddings -> Vector index/search
```

Each chunk carries `chunk_id`, `knowledge_id`, `topic_id`. BigQuery remains authoritative for full governance
metadata; the index only needs enough to join back.

## Query-time retrieval

```
User question
  -> Semantic search (vector similarity) -> Top N \
  -> Keyword search (lexical relevance)   -> Top N / -> Candidate merge -> Deduplicate -> Rerank
                                                                                             |
                                                                                             v
                                                                                     Governance filter
                                                                                             |
                                                                                             v
                                                                                   Top approved chunks -> Gemini
```

Ranking weights (semantic score + lexical score combination) are configurable, not fixed — start with a simple
weighted combination and tune later against a retrieval evaluation set (see below).

## Structured retrieval (not RAG)

Questions about the knowledge catalog, available topics, review status, analytics, or operational metadata are
answered through structured BigQuery tools (`query_health_topics`, `get_knowledge_record`, etc.), not RAG. Routing
between "needs RAG" and "needs structured lookup" is an agent/intent decision, not a retrieval-layer one.

## Retrieval evaluation

Maintain a small benchmark set: representative questions with expected relevant `knowledge_id`s. Compare
semantic-only, lexical-only, and hybrid retrieval on:

- Whether a relevant record appears in Top-K
- No-result rate
- Governance-rejection rate

This is what makes the hybrid choice evidence-based rather than assumed, and it's a natural artifact to point to in
review/interview discussion. Results and methodology should be written up here once the eval set exists.
