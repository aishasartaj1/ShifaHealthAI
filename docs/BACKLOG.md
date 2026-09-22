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
├── .github/workflows/        [x] pr.yml + deploy.yml (Phase 9)
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

### Phase 7 — Streaming — **done** (2026-09-21)
- [x] Event emission: `QUESTION_ASKED`/`RESPONSE_GENERATED` published server-side by `backend/src/api/chat.py` (the one place that reliably knows both happened); `SOURCE_OPENED`/`RELATED_TOPIC_OPENED`/`FEEDBACK_SUBMITTED` fired by the frontend via a new `POST /api/events` (fire-and-forget, never blocks the UI). No question/answer text ever captured — Section 16's privacy guidance, enforced by the schema itself (`backend/src/schemas/events.py`) having no free-text field
- [x] Terraform `pubsub` module: `shifahealth-events` topic + `shifahealth-events-streaming-sub` pull subscription, applied
- [x] `pipelines/streaming/`: Beam pipeline (`transforms.py` pure validation + `pipeline.py` DAG + `run.py` CLI with `--run-for-seconds` for bounded DEV demo runs) reading Pub/Sub → validate → `curated.fact_user_question`. Invalid events quarantine into a BigQuery table (`curated.quarantined_events`), not GCS like batch's quarantine — an unbounded streaming file sink needs window/trigger finalization for no real benefit at this volume; a streaming insert needs none of that
- [x] `scripts/refresh_analytics.py`: aggregates `curated.fact_user_question` into `semantic.question_analytics` (key/value metrics table, global + per-topic). A periodic re-runnable script, not continuous windowed streaming aggregation — same "simplest defensible option" reasoning as `build_index.py`, written up in DEVLOG
- [x] `GET /api/admin/analytics` + `AdminOverview.tsx` analytics section (5 stat tiles: questions asked, responses generated, avg latency, source opens, feedback up/down)
- [x] Bonus, not originally ticketed: related-topic chips now navigate to `/topics?topic=<id>` (deep link), and answers get a real 👍/👎 feedback control
- [x] Tests: 14 new backend tests (event schema/route validation, including a test that a client cannot fabricate `QUESTION_ASKED`/`RESPONSE_GENERATED`), 9 new streaming-pipeline tests (validation, normalization, native-datetime handling). 100+ tests total across the repo
- [x] **Real end-to-end verification**, not mocked: ran the actual Beam streaming pipeline against the real Pub/Sub subscription while firing real chat requests and interaction events; confirmed all 5 event types landed in `curated.fact_user_question` with correct structured fields; published two deliberately malformed messages directly to Pub/Sub and confirmed both were quarantined with accurate reasons; ran `refresh_analytics.py` and confirmed `GET /api/admin/analytics` returned the exact aggregated numbers; Playwright-verified the full browser flow (ask → source click → feedback click → related-topic click → deep-linked Topics page → Admin analytics tiles), zero console errors

### Phase 8 — Platform — **mostly done** (2026-09-21); `functions/` deferred, see Next action
- [x] Terraform `cloud_run` module (generic, reusable), instantiated 3x: `backend` (public), `agents` (IAM-gated, not network-gated — see below), `frontend` (public). All three **live and verified**: https://frontend-u7f3tlft2q-uc.a.run.app
- [x] Terraform `iam` module: one service account per service, least-privilege project roles, plus the scoped `backend`-SA-\>`roles/run.invoker`-on-`agents` binding (not project-wide) — the real, IAM-enforced trust boundary from architecture.md's Service Topology
- [x] Terraform `artifact_registry` module: one Docker repo, all three images built via Cloud Build (`gcloud builds submit`) and pushed
- [x] Secret Manager: `shifahealth-internal-api-key` (a real `random_password`, not the DEV placeholder), scoped `secretAccessor` grants to exactly the two services that need it
- [x] Real caller verification for `/internal/*`: Google-issued ID token (`google.oauth2.id_token.verify_oauth2_token`), checked against `agents`' service account email, with the shared-secret header kept only as an explicit local-dev fallback. Implemented **both directions** — `agents` calling `backend`'s `/internal/*`, and `backend` calling `agents`' `/invoke` (the second direction wasn't in the original ticket wording but is exactly the same problem and was needed to make the live deployment work at all)
- [x] Terraform `observability` module: two log-based metrics (request count, 5xx count) over Cloud Run's own request logs — deliberately no alert policies/notification channels (those need a real notification target nobody asked to create)
- [x] Dockerfiles for `backend/`, `agents/`, `frontend/` (frontend: multi-stage, nginx, `VITE_API_BASE_URL` baked in at build time via a build ARG)
- [ ] `functions/`: **not built this phase** — deferred to keep Phase 8 scoped to what was needed to get a live, working public deployment; see Next action

**Three real bugs found by actually deploying, not by reasoning in advance** (full writeup in DEVLOG):
1. `agents/requirements.txt` pinned a `fastapi` version incompatible with `google-adk`'s actual constraint — worked locally (pip had resolved a newer version there already) but failed in Cloud Build's clean install. Fixed by pinning to what was actually resolved.
2. Guessed Cloud Run's default URL format wrong (project-number-based) — the real format uses an opaque per-project+region hash. Fixed by deriving both services' URLs from a variable (`cloud_run_url_suffix`) instead of a (wrong) formula, which also happens to be the only way to avoid a genuine circular Terraform dependency between `backend` and `agents` each needing the other's URL.
3. `agents`' `INGRESS_TRAFFIC_INTERNAL_ONLY` silently blocked *everyone*, including `backend` itself — Cloud-Run-to-Cloud-Run internal calls need a Serverless VPC Access connector that was never set up; assumed (wrongly) it worked automatically. Fixed by switching to `INGRESS_TRAFFIC_ALL` + keeping IAM as the actual (and, it turns out, industry-standard) trust boundary.

### Phase 9 — CI/CD
- [x] `infra/terraform/modules/cicd/`: Workload Identity Federation (GitHub Actions → GCP, no service-account JSON keys) + a `shifahealth-ci` service account with deliberately narrow permissions — image push, Cloud Build trigger, Cloud Run revision deploy, `serviceAccountUser` on the 3 app SAs (scoped per-SA, not project-wide), plus read-only roles (`viewer`, `iam.securityReviewer`, `secretmanager.viewer`) so `terraform plan` in PRs gets a real diff. Deliberately **no** `terraform apply`-level roles (no `bigquery.admin`, no `resourcemanager.projectIamAdmin`) — applied via `terraform apply`, 15 resources created.
- [x] `.github/workflows/pr.yml`: backend/agents/pipelines pytest + ruff, seed-data validation (`scripts/validate_seed_data.py` + its own test), frontend `npm run lint` + `npm run build`, `terraform fmt -check`/`validate`/`plan` (auth'd via WIF, read-only)
- [x] `.github/workflows/deploy.yml`: on push to `main` — build 3 images via `gcloud builds submit` (frontend via its existing `cloudbuild.yaml` build-arg substitution), deploy via `gcloud run deploy` per service, then smoke-test backend `/health` and frontend `/`
- [x] Kept infra-provisioning (Terraform, manual `apply`) and app-deploy (`deploy.yml`, automatic on merge) conceptually separate — `deploy.yml` never calls `terraform apply`
- [x] Set `WORKLOAD_IDENTITY_PROVIDER` / `CI_SERVICE_ACCOUNT` as GitHub repo variables (`gh auth login` completed after initially being blocked, then `gh variable set` for both)
- [x] Tested `deploy.yml` for real by pushing to `main` — found and fixed **two more real permission gaps**, both only discoverable by actually running the build under the narrow CI identity (see DEVLOG's Phase 9 entry): `gcloud builds submit`'s GCS staging-bucket upload needs `storage.objectAdmin` on `<project>_cloudbuild`, and Cloud Build's default runtime service account (the project's default Compute Engine SA) needs `iam.serviceAccountUser` granted to the submitting identity. Full pipeline (build 3 images, deploy 3 services, smoke test) went green in 4m38s after both fixes.
- [ ] Test `pr.yml` for real (open a PR)

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

Set the two GitHub repo variables (`WORKLOAD_IDENTITY_PROVIDER`, `CI_SERVICE_ACCOUNT` — values in DEVLOG's Phase 9
entry) and open a real PR / push a commit to `main` to exercise `pr.yml` / `deploy.yml` for the first time. After
that: either (a) build `functions/` — one Cloud Function on the raw bucket's file-arrival event, publishing an
ingestion-signal message (small, explicitly optional per the plan) — or (b) start Phase 10 (Polish).

Note: `backend/src/services/trace_store.py` (agent traces) is still in-memory, not durable — that's a deliberate,
narrower scope than it might sound: Phase 7 built durable storage for *interaction* events
(`curated.fact_user_question`), not *agent* traces, which are a different concern the plan doesn't explicitly
ask to be persisted via streaming. Revisit only if a real need for durable trace history shows up.
