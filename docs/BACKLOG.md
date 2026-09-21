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

### Phase 3 — Batch pipeline — **done** (2026-09-21)
- [x] `pipelines/batch/`: Beam job (`transforms.py` pure logic + `pipeline.py` DAG + `run.py` CLI) — dedup (GroupByKey per ID field, ALL copies quarantined, no arbitrary winner), schema/enum/FK validation, `ai_eligible` enrichment
- [x] Quarantine path: invalid + duplicate records → `gs://<project>-quarantine/<run_id>/quarantine*.jsonl`, tagged with table + reason. Verified live: injected a bad row into `raw.raw_knowledge`, confirmed it landed in quarantine with the right reason and did NOT appear in curated/semantic, then cleaned up
- [x] Curated → semantic transforms: `curated.{dim_health_topic,dim_source,dim_knowledge,fact_medical_review}` → `semantic.{knowledge_catalog,approved_knowledge,agent_eligible_knowledge,topic_knowledge_summary}`. `fact_user_question`/`semantic.question_analytics` intentionally NOT built here — no data source populates them until Phase 7 (streaming)
- [x] Terraform `storage` module: `<project>-raw` + `<project>-quarantine` buckets, applied. Terraform `bigquery` module extended with the 8 curated/semantic table schemas (deferred from Phase 2), applied
- [x] Tests: `pipelines/batch/tests/test_transforms.py` (21 tests — valid/invalid cases per table, FK checks, `ai_eligible` truth table, duplicate handling, a regression test for BigQuery's native `date` objects). Ran the actual pipeline against `shifahealthai`: counts match exactly (33/38 eligible, matching Phase 2's preview)

### Phase 4 — Retrieval — **done** (2026-09-21)
- [x] `backend/src/retrieval/semantic.py`: `rank_by_similarity` (pure cosine, no numpy) + `embed_query`/`fetch_embedding_corpus` (Vertex AI `text-embedding-005` via `google-genai`, corpus from `semantic.knowledge_embeddings`)
- [x] `scripts/build_index.py`: embeds `semantic.agent_eligible_knowledge` (33 rows), writes `semantic.knowledge_embeddings`. Chunking is a no-op — summaries are already one short paragraph each, `chunk_id == knowledge_id`. Ran for real against `shifahealthai`; verified 33 rows × 768 dims
- [x] `backend/src/retrieval/lexical.py`: `rank_by_bm25` (via `rank-bm25`) over title+summary, corpus fetched fresh from `semantic.agent_eligible_knowledge` every call (no separate lexical index to go stale)
- [x] `backend/src/retrieval/hybrid.py`: `normalize_scores` (min-max) + `merge_and_rerank` (configurable `semantic_weight`/`lexical_weight`, dedupes by `knowledge_id`, a candidate from only one side gets 0 for the other)
- [x] `backend/src/retrieval/governance.py`: `fetch_currently_eligible_ids` (fresh query, not the embedding snapshot) + `filter_eligible` (pure)
- [x] `backend/src/retrieval/search.py`: `search_knowledge()` composing all of the above — the actual hybrid-RAG entrypoint, matching rag-design.md's diagram exactly
- [x] Tests: 22 backend tests (`test_hybrid.py`, `test_governance.py`, `test_semantic_retrieval.py`, `test_lexical_retrieval.py`) — merge/rerank weighting and top-n behavior, governance filter keeps-only-eligible/preserves-order/empty-set cases, cosine edge cases, BM25 exact-term-match
- [x] **Live drift test**: deleted `know_pcos_002` from `semantic.agent_eligible_knowledge` only (leaving its embedding in place — simulating eligibility changing after the index was built). Confirmed `semantic_search()` alone still returned it as the #1 match (0.839), but `search_knowledge()`'s governance re-check correctly dropped it from the final results. Restored via a batch-pipeline re-run

### Phase 5 — Agent — **done** (2026-09-21)
- [x] `agents/`: standalone Google ADK application, one `LlmAgent` (Gemini via Vertex AI). Dockerfile deferred to Phase 8 alongside backend's and frontend's (containerization grouped together, not piecemeal)
- [x] `agents/src/tools.py`: all 6 tools, each a thin `httpx` call into `backend`'s new `/internal/*` API (`backend/src/api/internal.py`) — **decided:** agent calls backend over HTTP, backend owns all BigQuery/Vertex AI retrieval code, agents/ holds no data-access credentials of its own (see architecture.md's Service Topology)
- [x] `backend/src/api/internal.py` + `backend/src/repositories/bigquery.py`: the 6 tools' backing endpoints (`search-knowledge`, `knowledge/{id}`, `sources/{id}`, `knowledge/{id}/eligibility`, `topics`, `topics/{id}/related`). Auth is a shared-secret header (`X-Internal-Api-Key`) — a deliberate DEV stand-in for real Cloud Run IAM ID-token verification, since backend needs public ingress for the frontend and can't rely on private-ingress IAM the way `backend -> agents` can. Phase 8 should replace this
- [x] Agent trace capture (`agents/src/trace.py`): tool name, args, result summary (counts only, never raw content), latency — wired via ADK's `before_tool_callback`/`after_tool_callback`, isolated per-request with a `contextvars.ContextVar`
- [x] `backend/src/services/agent_client.py`: backend's HTTP client for calling `agents`, tested with mocked HTTP and proven against a live `agents` instance. Not wired to a public route yet — that's Phase 6's `POST /api/chat`
- [x] Tests: 16 new `agents/` tests (mocked-HTTP tool contracts, pure trace-logic), 8 new `backend/` tests (internal API auth + routes, agent_client contract) — 46 tests total across both services, all hermetic (no live GCP calls)
- [x] **Real end-to-end verification** (not mocked): ran backend + agents together, called `/invoke` directly and via `AgentClient`, for real, against live Vertex AI Gemini + BigQuery. Confirmed: correct grounded, cited answers (matches the plan's own PCOS example); the diagnosis/treatment refusal guardrail triggers with zero tool calls; multi-turn session memory. Found and fixed a real bug in the process — recreating the ADK `Runner` per-request silently wiped session history every time; fixed with a module-level singleton `Runner` + `ContextVar`-based per-request trace isolation

### Phase 6 — Application — **done** (2026-09-21)
- [x] `POST /api/chat`, `GET /api/topics`, `GET /api/knowledge/{id}`, `GET /api/sources/{id}` — plus `GET /api/topics/{topic_id}/knowledge`, added beyond the original list because Topics.tsx needed something to show once a topic is selected (see DEVLOG)
- [x] Frontend `Assistant.tsx`: question input, grounded answer, source cards, related-topic chips, educational disclaimer — session id generated client-side, persists across turns in one visit
- [x] Frontend `Topics.tsx`: topic list -> click -> knowledge records for that topic, with review/content status badges
- [x] Admin console shell: `AdminOverview.tsx` (quality stats + per-topic table), `AgentObservability.tsx` (trace list + tool-call detail), `Governance.tsx` (ineligible-records table) — backed by `GET /api/admin/quality` (bundles Section 25's quality metrics with the Section 4.2 non-eligible-records view, since the plan specifies one endpoint for both), `GET /api/admin/agents` + `/agents/{trace_id}` (backed by an in-memory trace store — durable/cross-instance storage is Phase 7's job, not duplicated here)
- [x] Tests: 20 new backend tests (chat/topics/knowledge/admin routes + the pure `extract_candidate_knowledge_ids` helper + trace store), all hermetic. 91 tests total across the whole repo
- [x] **Real browser verification**, not just `curl`: used Playwright (headless Chromium) to drive the actual running app — asked a real question, confirmed grounded answer + 3 source cards + 1 related-topic chip rendered; clicked through Topics, Admin, Agent Observability, and Governance; captured screenshots of all 6 states; confirmed zero browser console errors. First time this project's UI was actually looked at rather than just its API

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
- [ ] Secret Manager wiring for runtime config/secrets (no secrets in Git, ever), including `internal_api_key`
- [ ] Replace `backend`'s `/internal/*` shared-secret auth (Phase 5's DEV stand-in) with real caller verification — either a Google-issued ID token check (`google.oauth2.id_token.verify_oauth2_token`) confirming the caller is `agents`' service account, or move `/internal/*` behind its own private-ingress boundary
- [ ] Terraform `observability` module: Cloud Logging/Monitoring baseline for both services
- [ ] Dockerfiles for `backend/`, `agents/`, and `frontend/` (grouped here rather than written piecemeal per phase)
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

Start Phase 7 (Streaming): emit `QUESTION_ASKED`/`RESPONSE_GENERATED`/`SOURCE_OPENED`/`RELATED_TOPIC_OPENED`/
`FEEDBACK_SUBMITTED` events from React/FastAPI, add the `pubsub` Terraform module, and a `pipelines/streaming/`
Beam job that validates/enriches/aggregates them into BigQuery — which is also the natural point to replace
Phase 6's in-memory trace store with real durable, cross-instance trace persistence.
