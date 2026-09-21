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

Requires `gcloud auth application-default login` once, so Terraform's Google provider can authenticate.
`terraform apply` enables the GCP APIs required by later phases (Cloud Run, BigQuery, Pub/Sub, Dataflow, Vertex
AI, etc.) on the target project — it does not yet provision any billable resources (no Cloud Run services,
buckets, or datasets exist until their respective phases land).

## Live demo

Not yet deployed.
