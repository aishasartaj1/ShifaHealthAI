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
review/interview discussion.

### Results (2026-09-22)

`scripts/retrieval_benchmark.json` (29 cases) + `scripts/eval_retrieval.py`, run against the live corpus (33
governed knowledge records):

```
python scripts/eval_retrieval.py --project shifahealthai
```

The script imports `backend/src/retrieval`'s actual modules directly rather than reimplementing scoring —
evaluating logic that isn't what's running in production would be worthless.

**24 grounded questions, hit@5 (governed results):**

| Method | Overall | Semantic-styled questions (n=13) | Lexical-styled questions (n=11) |
|---|---|---|---|
| Semantic-only | 24/24 | 13/13 | 11/11 |
| Lexical-only | 19/24 | 10/13 | 9/11 |
| Hybrid | 24/24 | 13/13 | 11/11 |

No-result rate was 0/24 for all three methods on this corpus. Semantic-only alone already hits every case here —
at 33 records, `text-embedding-005` generalizes well even across paraphrase/no-shared-keyword questions
("morning-after pill" -> "emergency contraception", "birth control" -> "contraception"). Lexical-only misses
exactly the questions tagged `semantic` in the benchmark (5/13 misses there vs 1/11 on `lexical`-tagged
questions) — BM25 can't bridge a paraphrase with zero shared tokens. **This result doesn't invalidate the hybrid
design** — semantic's ceiling here reflects a 33-row corpus where every record is short and topically distinct;
lexical retrieval is what keeps precision on exact terms (acronyms, named conditions) as the corpus grows past
the point where embedding similarity alone reliably separates near-duplicate entries, which is the regime this
benchmark is too small to exercise. The honest conclusion at this corpus size: semantic-only would currently
suffice, and hybrid's value here is insurance against a larger, more repetitive future corpus rather than a
measurable improvement at n=33.

**5 governance-rejection cases** (questions phrased to closely match 5 known-ineligible records — one
`NEEDS_REVIEW`, two `STALE`, one `EXPIRED`, one more `NEEDS_REVIEW`): **0/5 ineligible records ever appeared as a
raw retrieval candidate.** This was initially surprising, then revealing: `semantic.agent_eligible_knowledge` —
the table both `lexical_search`'s corpus fetch and `governance.fetch_currently_eligible_ids` query — is itself
populated by the batch pipeline (Phase 3) from *already-governed* rows. Ineligible content never enters the
retrieval corpus in the first place; that's an earlier, stronger enforcement point than "generate a candidate,
then filter it out."

That raised the real question `governance.py`'s own docstring poses: does the query-time re-check
(`filter_eligible` against `fetch_currently_eligible_ids`) actually catch anything, or is it unreachable code?
Tested directly rather than assumed: temporarily deleted `know_mc_001` (a currently-eligible, unrelated record)
from `semantic.agent_eligible_knowledge` only — not from `semantic.knowledge_embeddings`, the separately
-snapshotted vector index `scripts/build_index.py` last populated. This reproduces exactly the scenario the
docstring describes: a record eligible when the index was built, since become ineligible before a later query.
Result: `semantic_search` still returned `know_mc_001` as the #1 raw candidate (the stale index doesn't know
about the change), and `governance.filter_eligible` correctly dropped it once cross-checked against the live
`fetch_currently_eligible_ids` call. The row was restored immediately after and verified byte-for-byte identical
to the captured original, with the corpus back at 33 rows.

**Conclusion:** two independent, correctly-functioning enforcement points, not one redundant one — batch-pipeline
governance keeps ineligible content out of the corpus altogether, and the query-time re-check exists
specifically for the gap between an index snapshot and live eligibility, which this test confirms it actually
closes.
