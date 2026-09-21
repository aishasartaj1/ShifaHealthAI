# Implementation Backlog

Derived from Sections 27–30 of the architecture plan. This is the working backlog — check items off as they land,
and keep [architecture.md](architecture.md)'s decision log updated when reality deviates from a plan item.

Ground rules (from the handoff instructions, keep re-reading these before adding scope):

- Build incrementally; the project stays demoable after every phase.
- Don't add a service to match a job-description keyword — every deployed component needs a concrete responsibility.
- DEV-only infrastructure; keep Terraform modular so Stage/Prod *could* reuse it without deploying it now.
- BigQuery is the governance/semantic authority, never the vector store.
- Hybrid retrieval = semantic + lexical → merge/rerank → **final governance check** before generation.
- No raw chain-of-thought in observability — tool/retrieval metadata only.
- Public/synthetic data only, no PHI, anywhere (seed data, demo events, logs).
- Prefer a working vertical slice over breadth; optional services (Composer, etc.) come after the vertical slice works.
- Every phase needs automated tests for its own layer (transformations, governance eligibility, retrieval merging,
  agent tool contracts, API responses) — not deferred to a "testing phase."

## Repository structure — Section 27

Status: **done** (scaffolded 2026-09-21).

```
ShifaHealthAI/
├── frontend/                 [x] src/{pages,components,api,types}
├── backend/                  [x] src/{api,retrieval,repositories,services,schemas,config}, tests/
├── agents/                   [x] standalone ADK agent service (root-level, own Cloud Run deployment — see architecture.md "Service topology")
├── pipelines/                [x] batch/, streaming/
├── functions/                [x]
├── data/                     [x] seed/, synthetic/
├── infra/terraform/          [x] modules/{storage,bigquery,pubsub,cloud_run,functions,artifact_registry,iam,observability}, environments/dev/
├── scripts/                  [x]
├── docs/                     [x] architecture.md, data-model.md, governance.md, rag-design.md, demo-script.md, BACKLOG.md, DEVLOG.md
├── .github/workflows/        [x] (empty — CI added in Phase 9)
├── README.md                 [x]
└── .gitignore                [x]
```

`agents/` is a deliberate deviation from the plan's Section 27 tree (which nested agent code under `backend/src/agents/`)
— it's root-level because it deploys as its own Cloud Run service, not as backend code. See the 2026-09-21 entries
in [architecture.md](architecture.md#decision-log) and [DEVLOG.md](DEVLOG.md).

Remaining structural work is filling these directories with real content per the phases below — no further
directories should be needed for the MVP.

## Implementation sequence — Section 29

Each phase below is broken into concrete tickets. Phases are sequential in intent, but a phase can start once its
prerequisites exist, not strictly after the previous phase's polish is finished.

### Phase 1 — Foundation — **done** (2026-09-21)
- [x] Backend: FastAPI app skeleton (`backend/src/main.py`), health-check route, config loading (`backend/src/config/`)
- [x] Backend: local dev instructions (README "Setup" section)
- [x] Frontend: Vite + React + TypeScript scaffold, base routing shell (`/`, `/topics`, `/admin`)
- [x] Frontend: local dev instructions (README "Setup" section)
- [x] GCP: project created (`shifahealthai`, no org); required APIs enabled via `terraform apply`
- [x] Terraform: base provider/backend config (`infra/terraform/environments/dev/backend.tf`, `main.tf`, `variables.tf`, `outputs.tf`, `terraform.tfvars.example`)
- [x] `.env.example` for backend and frontend (no real secrets)

### Phase 2 — Data model — **done** (2026-09-21)
- [x] Seed data: `data/seed/health_topics.csv`, `sources.csv`, `knowledge_metadata.csv`, `medical_reviews.csv`, `safety_rules.json` — 6 topics, 9 real public sources, 38 knowledge records
- [x] Terraform `bigquery` module: `raw`/`curated`/`semantic` datasets + the 4 `raw` tables (curated/semantic *tables* deferred to Phase 3, once transform logic exists — see module's `main.tf` comment); applied against `shifahealthai`
- [x] `scripts/seed_bigquery.py`: loads seed data into `raw.*`; run against `shifahealthai`, row counts verified
- [x] Governance fields present in raw schema: `review_status`, `source_status`, `content_status`, `content_version`. **`ai_eligible` deliberately excluded from raw** — it's a derived flag, computed by the Phase 3 Dataflow transform from the other three, not authored by hand (see DEVLOG)
- [x] Tests: `scripts/validate_seed_data.py` + `scripts/test_validate_seed_data.py` — schema, enum, and foreign-key checks, run before any BigQuery load

### Phase 3 — Batch pipeline
- [ ] `pipelines/batch/`: Beam/Dataflow job — schema validation, normalization, dedup, metadata enrichment, quality checks
- [ ] Quarantine path: invalid records routed to GCS quarantine bucket/prefix, not dropped
- [ ] Curated → semantic transforms (raw → curated dimensional tables → semantic AI-ready views/tables)
- [ ] Terraform `storage` module: raw + quarantine buckets
- [ ] Tests: transformation unit tests (valid/invalid record cases), quarantine routing test

### Phase 4 — Retrieval
- [ ] `backend/src/retrieval/semantic.py`: embedding + vector search against `semantic.agent_eligible_knowledge`-derived chunks
- [ ] `scripts/build_index.py`: chunk + embed eligible knowledge, populate vector index
- [ ] `backend/src/retrieval/lexical.py`: keyword/BM25-style search
- [ ] `backend/src/retrieval/hybrid.py`: merge, dedupe, rerank (configurable weights)
- [ ] `backend/src/retrieval/governance.py`: query-time re-validation of candidate `knowledge_id`s against BigQuery
- [ ] Tests: hybrid merge/rerank logic, governance filter rejects ineligible candidates

### Phase 5 — Agent
- [ ] `agents/`: standalone Google ADK application (own `pyproject.toml`/requirements, own Dockerfile) — single Gemini orchestrating agent
- [ ] `agents/tools.py` (or ADK-idiomatic equivalent): `search_knowledge`, `get_knowledge_record`, `get_source_metadata`, `check_content_eligibility`, `query_health_topics`, `find_related_topics` — these call into `backend`'s retrieval/BigQuery code, so decide: agent calls backend's internal HTTP API, or agent imports a shared retrieval package directly
- [ ] Agent trace capture: intent, topic, candidate counts, tools called, timing — no raw chain-of-thought (ADK's built-in tracing may cover most of this)
- [ ] `backend/src/services/agent_client.py`: backend's HTTP client for calling the private `agents` Cloud Run service (Phase 1–8 local dev equivalent: call `agents` on localhost)
- [ ] Tests: each tool's contract (input/output shape, governance enforcement), orchestrator intent routing (RAG vs. structured), backend↔agents client contract

### Phase 6 — Application
- [ ] `POST /api/chat`, `GET /api/topics`, `GET /api/knowledge/{id}`, `GET /api/sources/{id}` endpoints
- [ ] Frontend `Assistant.tsx`: question input, grounded answer, source cards, related topics, educational disclaimer
- [ ] Frontend `Topics.tsx`: topic/knowledge explorer
- [ ] Admin console shell: `AdminOverview.tsx`, `AgentObservability.tsx`, `Governance.tsx` + `GET /api/admin/quality`, `/admin/agents`, `/admin/agents/{trace_id}`
- [ ] Tests: API response schema tests, basic frontend component tests

### Phase 7 — Streaming
- [ ] Event emission from React/FastAPI for `QUESTION_ASKED`, `RESPONSE_GENERATED`, `SOURCE_OPENED`, `RELATED_TOPIC_OPENED`, `FEEDBACK_SUBMITTED`
- [ ] Terraform `pubsub` module: topic(s) + subscription(s)
- [ ] `pipelines/streaming/`: Dataflow job — validate event, enrich topic/type, aggregate metrics → BigQuery
- [ ] `GET /api/admin/analytics` + `AdminOverview.tsx` analytics section
- [ ] Tests: event schema validation, aggregation logic

### Phase 8 — Platform
- [ ] Terraform `cloud_run` module, instantiated twice: `backend` (public ingress) and `agents` (private/internal ingress, no public access)
- [ ] Terraform `iam` module: dedicated service account per Cloud Run service; grant `backend`'s SA `roles/run.invoker` on the `agents` service specifically (not project-wide) — the enforced trust boundary from architecture.md's "Service topology"
- [ ] Terraform `artifact_registry` module: repository for both container images
- [ ] Secret Manager wiring for runtime config/secrets (no secrets in Git, ever)
- [ ] Terraform `observability` module: Cloud Logging/Monitoring baseline for both services
- [ ] `functions/`: one Cloud Function (raw-bucket file-arrival → ingestion-request event)

### Phase 9 — CI/CD
- [ ] `.github/workflows/`: PR pipeline — backend tests/lint, frontend tests/build, `terraform fmt`/`validate`/`plan`
- [ ] `.github/workflows/`: main pipeline — build container(s), push to Artifact Registry, deploy DEV Cloud Run, smoke test
- [ ] Keep infra-provisioning workflow and app-deploy workflow conceptually separate

### Phase 10 — Polish
- [ ] Retrieval evaluation: benchmark question set + expected `knowledge_id`s, semantic-vs-lexical-vs-hybrid comparison (write up in [rag-design.md](rag-design.md))
- [ ] `scripts/generate_demo_events.py`: synthetic demo traffic for analytics screenshots
- [ ] README: reproducible setup instructions from a clean DEV environment, live demo link, limitations, screenshots
- [ ] Architecture docs updated to reflect what was actually built (decision log in [architecture.md](architecture.md))

## MVP Definition — Section 28

Demo-ready when **all** of the following work end-to-end:

- [ ] React assistant reachable through a live URL
- [ ] FastAPI backend and the ADK agents service both run on Cloud Run (public + private respectively)
- [ ] At least 5 women's-health topics and 30–50 governed knowledge records available
- [ ] BigQuery contains raw, curated, and semantic datasets
- [ ] Batch Dataflow pipeline transforms source data and quarantines invalid records
- [ ] Hybrid semantic + lexical retrieval returns relevant knowledge
- [ ] Governance filtering prevents non-eligible content from reaching generation
- [ ] Gemini uses controlled tools and returns grounded educational answers with sources
- [ ] Pub/Sub → Dataflow → BigQuery processes demo interaction events
- [ ] Admin console shows data quality, governance, analytics, and agent traces
- [ ] Terraform provisions the DEV infrastructure
- [ ] GitHub Actions validates/tests/builds/deploys the application
- [ ] README includes architecture, setup, live demo link, limitations, and screenshots

## Deferred until after the core demo — Section 30

Do **not** build these until the MVP above is working end-to-end, even if a phase ticket seems related:

- Cloud Composer deployment
- Stage and Production environments
- Complex authentication/RBAC
- Large-scale corpus ingestion
- Advanced reranking models
- Multiple independent agents
- Long-term personalized user health memory
- Production compliance work
- Complex third-party healthcare integrations

## Next action

Start Phase 3 (Batch pipeline): a Beam/Dataflow job that reads `raw.*`, validates/normalizes, computes
`ai_eligible` (the real transform logic Phase 2 deferred), routes invalid records to GCS quarantine, and writes
`curated.*`/`semantic.*`. The `storage` Terraform module (raw + quarantine buckets) lands alongside it.
