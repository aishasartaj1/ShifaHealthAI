# ShifaHealth AI

**Governed Agentic Women's Health Knowledge Platform** — a DEV-only, publicly-deployable portfolio project on Google Cloud Platform.

> Status: scaffolding stage. See [docs/BACKLOG.md](docs/BACKLOG.md) for the implementation plan and current phase.

## What this is

ShifaHealth AI transforms structured metadata and public/synthetic women's-health educational content into governed,
AI-ready BigQuery data products. A Vertex AI Gemini agent answers educational questions using hybrid (semantic +
lexical) retrieval, validates every candidate against governance metadata before generation, and calls controlled
tools for structured data access. An admin-style console exposes the governance, data-quality, retrieval, and agent
observability behind the assistant.

This is intentionally a **DEV-only demo system**, not a production healthcare platform. It uses public and synthetic
data only — no PHI — and does not provide diagnosis, treatment, or personalized medical advice.

## Architecture at a glance

```
Public/synthetic data -> Cloud Storage -> Dataflow (validate/normalize) -> BigQuery (raw -> curated -> semantic)
                                                                                |
                                                        +-----------------------+------------------------+
                                                        |                                                |
                                          AI-eligible knowledge (chunk+embed)                  Structured SQL tools
                                                        |                                                |
                                      Semantic vector search + Keyword search -> Hybrid rerank            |
                                                        |                                                |
                                                  Governance check <-----------------------------------+
                                                        |
                                          Vertex AI Gemini agent orchestrator
                                                        |
                                              FastAPI (Cloud Run) -> React/Vite UI
                                                        |
                                    Women's Health Assistant        AI/Data Operations Console

Application events: React/FastAPI -> Pub/Sub -> Dataflow -> BigQuery -> Analytics Console
Platform: Terraform -> DEV infra | GitHub Actions -> test/validate/build/deploy | IAM + Secret Manager + Logging
```

Full detail lives in [docs/architecture.md](docs/architecture.md).

## Repository layout

```
ShifaHealthAI/
├── frontend/            React + TypeScript + Vite (Assistant UI, Admin console)
├── backend/              FastAPI service: public API, retrieval, repositories, governance
├── agents/               Standalone Google ADK agent service (own Cloud Run deployment, private ingress)
├── pipelines/            Dataflow/Beam batch + streaming jobs
├── functions/            Cloud Function(s) for event-driven ingestion signals
├── data/                 Seed + synthetic demo data (no PHI)
├── infra/terraform/      Modular Terraform, DEV environment only
├── scripts/              Seeding, index-building, demo-event generation utilities
├── docs/                 Architecture, data model, governance, RAG design, demo script
└── .github/workflows/    CI/CD: test, validate, build, deploy DEV
```

## Docs

- [Architecture](docs/architecture.md)
- [Data model](docs/data-model.md)
- [Governance model](docs/governance.md)
- [Hybrid RAG design](docs/rag-design.md)
- [Demo script](docs/demo-script.md)
- [Implementation backlog](docs/BACKLOG.md)
- [Development log](docs/DEVLOG.md) — chronological build journal: choices, deviations, interview notes

## Scope

In scope: women's-health educational knowledge, public/synthetic data, one DEV environment, hybrid RAG + structured
SQL retrieval, agentic tool calling with governance checks, Terraform + CI/CD + observability.

Out of scope: diagnosis/treatment/personalized medical advice, real PHI, Stage/Prod deployment, production HIPAA
compliance certification. See [docs/BACKLOG.md](docs/BACKLOG.md#deferred-until-after-the-core-demo) for what's
deliberately deferred.

## Setup

Reproducible for Phase 1 (backend + frontend skeletons, no live GCP integrations yet). This section grows as each
later phase lands.

### Backend (FastAPI)

```bash
cd backend
python -m venv .venv
.venv/Scripts/activate       # macOS/Linux: source .venv/bin/activate
pip install -r requirements-dev.txt
cp .env.example .env
pytest                       # should show 1 passed
uvicorn src.main:app --reload --port 8000
```

Health check: `curl http://localhost:8000/health`

### Frontend (React + Vite)

```bash
cd frontend
npm install
cp .env.example .env
npm run dev                  # http://localhost:5173
npm run build                # type-check + production bundle
```

### Infrastructure (Terraform, DEV only)

```bash
cd infra/terraform/environments/dev
cp terraform.tfvars.example terraform.tfvars   # edit project_id if not using shifahealthai
terraform init
terraform plan
terraform apply
```

Requires `gcloud auth application-default login` once, so Terraform's Google provider can authenticate. If ADC's
quota project doesn't match your target project, also run `gcloud auth application-default set-quota-project
<project_id>` — otherwise Python client libraries (e.g. `seed_bigquery.py` below) will get a 403 billing against
the wrong project.

`terraform apply` enables the required GCP APIs and provisions:
- `raw`/`curated`/`semantic` BigQuery datasets, the 4 `raw` tables, the 4 `curated` tables, and the 4 `semantic`
  tables (schemas only — Terraform owns schema, the batch pipeline owns data)
- `<project_id>-raw` and `<project_id>-quarantine` GCS buckets

It does not yet provision Cloud Run or Pub/Sub resources — those land in their respective phases.

### Seed data (Phase 2)

```bash
cd backend && .venv/Scripts/pip install -r ../scripts/requirements.txt   # or use scripts/ own venv
cd ..
python scripts/validate_seed_data.py           # schema/referential-integrity check, no GCP calls
python scripts/seed_bigquery.py --project shifahealthai
```

`data/seed/` holds 6 topics and 38 knowledge records (synthetic educational summaries, each citing a real public
source — see [docs/DEVLOG.md](docs/DEVLOG.md) for the sourcing approach). `ai_eligible` is intentionally not in
this seed data — it's a governance flag computed downstream by the batch pipeline, not authored by hand.

### Batch pipeline (Phase 3)

```bash
cd pipelines/batch
python -m venv .venv
.venv/Scripts/activate
pip install -r requirements-dev.txt
pytest tests/                                  # pure transform-logic tests, no GCP calls
python run.py --project shifahealthai --quarantine-bucket shifahealthai-quarantine
```

Reads `raw.*`, validates + dedupes + enriches, writes `curated.*` and `semantic.*` (`WRITE_APPEND` onto tables the
script truncates first — full-refresh-per-run semantics), and routes anything that fails validation to
`gs://<project_id>-quarantine/<run_id>/quarantine*.jsonl` instead of dropping it. Runs on Beam's `DirectRunner` by
default — real reads/writes against BigQuery + GCS, just executed locally rather than as a managed Dataflow job
(appropriate at this data volume; pass `--runner DataflowRunner --temp-location gs://... --staging-location
gs://...` to submit it as an actual Dataflow job instead).

### Retrieval (Phase 4)

```bash
cd backend
.venv/Scripts/pip install -r requirements.txt   # adds google-genai, rank-bm25 to the Phase 1 backend env
cd ..
python scripts/build_index.py --project shifahealthai   # embeds semantic.agent_eligible_knowledge -> semantic.knowledge_embeddings
cd backend && .venv/Scripts/pytest tests/ -q
```

`backend/src/retrieval/` implements the hybrid RAG design from [docs/rag-design.md](docs/rag-design.md):
`semantic.py` (cosine similarity over Vertex AI embeddings) + `lexical.py` (BM25) → `hybrid.py` (normalize +
weighted merge/rerank) → `governance.py` (re-checks each candidate against BigQuery's *current* eligibility,
not the embedding snapshot) → `search.py`'s `search_knowledge()` ties it together. Re-run `build_index.py`
whenever the batch pipeline changes `agent_eligible_knowledge`; the lexical corpus and governance check always
query BigQuery fresh, so only the embeddings can go stale between pipeline runs.

### Agent (Phase 5)

Port convention for local dev: `backend` on **8000**, `agents` on **8001**, `frontend` on **5173**.

```bash
# terminal 1 - backend (exposes /internal/* for the agent's tools)
cd backend && .venv/Scripts/uvicorn src.main:app --port 8000

# terminal 2 - agents (standalone ADK service)
cd agents
python -m venv .venv
.venv/Scripts/activate
pip install -r requirements-dev.txt
cp .env.example .env
pytest tests/ -q                        # mocked-HTTP tool tests + pure trace-logic tests, no live calls
uvicorn src.main:app --port 8001

# terminal 3 - talk to it
curl -X POST http://localhost:8001/invoke -H "Content-Type: application/json" \
  -d '{"message": "Can PCOS cause irregular periods?", "user_id": "demo"}'
```

`agents/` is a standalone [Google ADK](https://google.github.io/adk-docs/) app — one `LlmAgent` (Gemini via
Vertex AI) with the plan's six tools (Section 12), each a thin HTTP call into `backend`'s `/internal/*` API
(`agents/src/tools.py`); `backend` owns all BigQuery/Vertex AI retrieval access, `agents` owns none. Tool-call
observability (`agents/src/trace.py`) is wired via ADK's `before_tool_callback`/`after_tool_callback`, isolated
per-request with a `contextvars.ContextVar` so concurrent requests don't cross-contaminate traces. Session state
(multi-turn memory) lives in one process-lifetime `InMemoryRunner` — recreating the runner per request was a real
bug caught during Phase 5 (see [docs/DEVLOG.md](docs/DEVLOG.md)), not just a hypothetical one.

`backend/src/services/agent_client.py` is backend's HTTP client for calling `agents`, proven against a live
`agents` instance. Wired to a public route in Phase 6 below.

### Application (Phase 6)

```bash
# terminal 1 - backend
cd backend && .venv/Scripts/uvicorn src.main:app --port 8000

# terminal 2 - agents
cd agents && .venv/Scripts/uvicorn src.main:app --port 8001

# terminal 3 - frontend
cd frontend
npm install
cp .env.example .env
npm run dev   # http://localhost:5173
```

Open `http://localhost:5173`. `/` is the Women's Health Assistant (ask a question, get a grounded answer with
source cards and related-topic chips); `/topics` is the topic/knowledge explorer; `/admin`,
`/admin/agents`, `/admin/governance` are the AI/Data Operations Console (data-quality stats, agent traces,
non-eligible-records view).

Public API surface (`backend/src/api/`): `POST /api/chat`, `GET /api/topics`, `GET /api/topics/{topic_id}/knowledge`
(added beyond the plan's original list — the topic explorer needed something to show once a topic is selected),
`GET /api/knowledge/{id}`, `GET /api/sources/{id}`, `GET /api/admin/quality`, `GET /api/admin/agents` +
`/agents/{trace_id}`. `POST /api/chat` calls `agents` via `agent_client.py`, then builds source cards and
related topics from the agent's trace (not by parsing citations out of its prose — the trace now carries the
actual `knowledge_id`s a `search_knowledge` call surfaced, not just a count).

Agent traces are held in an in-memory store (`backend/src/services/trace_store.py`) — bounded, process-local,
lost on restart. That's deliberately unchanged by Phase 7 below: Phase 7 built durable storage for *interaction*
events, not agent traces, which are a different, narrower concern the plan doesn't ask to be streamed.

```bash
cd backend && .venv/Scripts/pytest tests/ -q   # 58 tests, all hermetic
cd frontend && npm run build                   # type-check + production bundle
```

### Streaming (Phase 7)

```bash
# terminal 4 - streaming pipeline (bounded run for DEV; a real Dataflow job runs indefinitely)
cd pipelines/streaming
python -m venv .venv
.venv/Scripts/activate
pip install -r requirements-dev.txt
pytest tests/ -q   # pure validation-logic tests, no GCP calls
python run.py --project shifahealthai --subscription shifahealth-events-streaming-sub \
  --runner BundleBasedDirectRunner --run-for-seconds 90
```

Use `--runner BundleBasedDirectRunner` explicitly for local runs — Beam 2.76's default local runner ("Prism")
doesn't yet support `ReadFromPubSub`; `BundleBasedDirectRunner` is the one that does (see
[docs/DEVLOG.md](docs/DEVLOG.md) for how this was diagnosed).

Reads `shifahealth-events-streaming-sub`, validates each event, writes valid ones to
`curated.fact_user_question` and invalid ones to `curated.quarantined_events` (both via streaming insert — no
GCS quarantine file here, unlike batch; see that table's schema comment for why). Events are published by:
- `backend/src/api/chat.py`, server-side, for `QUESTION_ASKED`/`RESPONSE_GENERATED` (no user-fireable equivalent)
- `POST /api/events`, called by the frontend, for `SOURCE_OPENED`/`RELATED_TOPIC_OPENED`/`FEEDBACK_SUBMITTED`

No question or answer text is ever captured in these events — see `backend/src/schemas/events.py`'s docstring.

```bash
python scripts/refresh_analytics.py --project shifahealthai
```

Aggregates `curated.fact_user_question` into `semantic.question_analytics` (global + per-topic metrics). A
small re-runnable script, not continuous streaming aggregation — re-run it after any batch of new events lands.
`GET /api/admin/analytics` serves the result; `AdminOverview.tsx`'s "Interaction analytics" section renders it.

## Live demo

Not yet deployed.
