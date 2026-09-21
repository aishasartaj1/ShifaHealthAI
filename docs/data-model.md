# Data Model

## Structured inputs (seed/synthetic, no PHI)

- `health_topics.csv`
- `sources.csv`
- `knowledge_metadata.csv`
- `medical_reviews.csv`
- `safety_rules.json`

## Unstructured inputs

Public women's-health educational documents/articles from reputable sources, with source attribution and metadata
retained. Never present scraped third-party text as proprietary ShifaHealth content.

## Streaming event inputs

- `QUESTION_ASKED`
- `RESPONSE_GENERATED`
- `SOURCE_OPENED`
- `RELATED_TOPIC_OPENED`
- `FEEDBACK_SUBMITTED`

No sensitive/identifying health information is collected in these events — synthetic demo questions and anonymous
operational telemetry only.

## Batch pipeline (Dataflow)

```
Cloud Storage /raw -> Dataflow
  -> schema validation
  -> normalization
  -> deduplication
  -> metadata enrichment
  -> quality checks
  --invalid--> GCS quarantine
  --valid----> BigQuery raw -> curated -> semantic
```

Dataflow must perform real transformations: normalize fields, validate required metadata, standardize
topic/source identifiers, flag invalid review states, route bad records to quarantine.

## BigQuery layers

### Raw

- `raw.raw_knowledge`
- `raw.raw_sources`
- `raw.raw_reviews`
- `raw.raw_topics`

### Curated (dimensional)

- `curated.dim_health_topic`
- `curated.dim_source`
- `curated.dim_knowledge`
- `curated.fact_medical_review`
- `curated.fact_user_question`

### Semantic / AI-ready (business-facing contract — the AI system depends only on this layer, never on raw)

- `semantic.knowledge_catalog`
- `semantic.approved_knowledge`
- `semantic.agent_eligible_knowledge`
- `semantic.topic_knowledge_summary`
- `semantic.question_analytics`

## Knowledge governance fields

| Field | Purpose |
|---|---|
| `knowledge_id` | Stable business identifier used across BigQuery and retrieval indexes |
| `topic_id` | Maps knowledge to a governed women's-health topic |
| `source_id` | Identifies the source organization/document |
| `review_status` | `APPROVED` / `NEEDS_REVIEW` / `EXPIRED` |
| `source_status` | `ACTIVE` / `INACTIVE` |
| `content_status` | `CURRENT` / `STALE` |
| `ai_eligible` | Final flag determining whether content may be used as agent context |
| `published_date` | Source publication metadata where available |
| `last_reviewed_date` | Governance metadata for the demo |
| `content_version` | Supports version-aware traceability |

See [governance.md](governance.md) for the eligibility pipeline and enforcement points.

## Vector index chunk metadata

Each chunk carries `chunk_id`, `knowledge_id`, `topic_id`. BigQuery remains the source of truth for full governance
metadata — the vector store never becomes an independent authority.

## MVP data volume target

~30–50 curated knowledge records across 5–8 topics, with strong source metadata and governance — breadth is
deliberately limited in favor of governance quality.
