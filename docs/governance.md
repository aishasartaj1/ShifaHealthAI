# Governance Model

BigQuery is the single governance authority. The vector index is retrieval infrastructure only — it never decides
eligibility.

## Eligibility pipeline

```
Raw content -> Validation -> valid -> Curated -> Governance checks -> Available to AI retrieval/generation
                           -> invalid -> Quarantine

Governance checks (all must pass):
  - review_status == APPROVED
  - source_status == ACTIVE
  - content_status == CURRENT
  - ai_eligible == TRUE
```

## Enforcement points

Governance is checked **before generation**, not just at ingestion:

1. At ingestion/curation time — records failing validation are quarantined, not silently dropped.
2. At index-build time — only rows resolvable to `semantic.agent_eligible_knowledge` are chunked/embedded.
3. At query time — every candidate `knowledge_id` returned by semantic or lexical retrieval is re-validated
   against current BigQuery governance fields before it can become grounding context. A record can become
   ineligible after it was indexed (e.g. review expires); the query-time check is what catches that, so retrieval
   never trusts the vector store's snapshot as final truth.

## Security & safety rules that follow from this model

- Public and synthetic data only; no PHI.
- No user identity stored alongside health questions in the demo.
- Least-privilege service accounts; secrets in Secret Manager, never in Git.
- Agent data access restricted to controlled tools and semantic data products — no unrestricted raw-table access.
- Unapproved/stale knowledge is excluded before generation, not filtered after the fact.
- Operational logs capture metadata (tool calls, candidate counts, latency), not unnecessary sensitive content.
- The assistant is clearly labeled educational — not diagnostic, not a substitute for medical care.
- The demo never claims HIPAA compliance.

## Data quality dimensions tracked

| Metric | Example |
|---|---|
| Completeness | Required source/topic/review fields populated |
| Validity | Review status and identifiers conform to allowed values |
| Uniqueness | No duplicate knowledge/source identifiers |
| Freshness | Age since last successful ingestion/index refresh |
| AI eligibility | Percentage of curated knowledge currently eligible for retrieval |

These are surfaced in the AI/Data Operations Console under Governance and Data Quality.
