# Architecture

Source of truth: *ShifaHealth AI — Architecture & Implementation Plan* (the kickoff document; not checked into this
repo). This file tracks the architecture as actually implemented and notes any deviations with rationale; it does
not restate the full source document.

## Principles (non-negotiable)

| Principle | Decision |
|---|---|
| BigQuery is authoritative | Structured business entities, metadata, review status, AI eligibility, analytics, and governance live in BigQuery. |
| Vector index is retrieval infrastructure | Embeddings/chunks support semantic retrieval; the vector store is not the governance authority. |
| Hybrid retrieval | Combine semantic similarity with lexical/keyword relevance, then rerank and govern results. |
| Govern before generation | Only AI-eligible, current, approved content can become generation context. |
| Controlled agent access | The Gemini agent accesses data through explicit tools rather than unrestricted raw-table access. |
| Separate data and serving paths | Batch/stream processing is independent from synchronous user-response serving. |
| DEV-only deployment | Terraform modules remain reusable, but only a DEV environment is provisioned. |
| Agent runtime is its own service | The ADK agent runs as a separate, private Cloud Run service from the FastAPI backend, invoked over authenticated service-to-service HTTP. See "Service topology" below. |

## High-level flow

```
PUBLIC / SYNTHETIC DATA
  -> Cloud Storage (raw)
  -> Dataflow (validate/normalize) --invalid--> GCS quarantine
  -> BigQuery: RAW -> CURATED -> SEMANTIC
       -> AI-eligible knowledge -> chunk+embed -> Vertex AI embeddings -> Vector index/search
       -> Structured SQL tools (direct semantic-layer queries)
  -> [Semantic vector search + Keyword search] -> Hybrid ranker -> Governance check
  -> Vertex AI Gemini agent orchestrator (controlled tools)
  -> FastAPI (Cloud Run) -> React/Vite UI
       -> Women's Health Assistant
       -> AI/Data Operations Console

Application events: React/FastAPI -> Pub/Sub -> Dataflow -> BigQuery -> Analytics Console
Platform: Terraform -> DEV infra | GitHub Actions -> test/validate/build/deploy DEV | IAM + Secret Manager + Logging/Monitoring
```

## Service topology

The plan's single "FastAPI (Cloud Run)" box is implemented as **two** Cloud Run services, not one — see the
2026-09-21 decision-log entry for why:

```
React/Vite UI
     |
     v  POST /api/chat, GET /api/topics, /api/admin/*   (public)
FastAPI backend  ── Cloud Run service "backend", public ingress
     |
     v  internal call, IAM-authenticated (service account invoker binding, no public ingress)
ADK agent service ── Cloud Run service "agents", private ingress
     |
     v
Vertex AI Gemini + retrieval/governance tools
```

- `backend/` — FastAPI. Public entrypoint for the frontend. Owns everything that *isn't* agent reasoning:
  topics/sources/knowledge lookups, admin/governance/analytics endpoints, request validation, session/trace
  bookkeeping, forwarding chat requests to the agent service and returning its response.
- `agents/` — a standalone [Google ADK](https://google.github.io/adk-docs/) application. Owns the orchestrating
  Gemini agent and its tools (`search_knowledge`, `get_knowledge_record`, `get_source_metadata`,
  `check_content_eligibility`, `query_health_topics`, `find_related_topics`). Deployed as its own Cloud Run
  service with **no public ingress** — only the backend's service account is granted `roles/run.invoker` on it.
- Why split them: mirrors how ADK is meant to run (as its own agent runtime, not embedded inline in an arbitrary
  web framework), gives a real IAM-enforced trust boundary to point to ("the web tier cannot reach Gemini or the
  retrieval tools directly — only the agent service can, and only the backend can reach the agent service"), and
  keeps agent code deployable/scalable independently of the web-serving code. Cost: one more Cloud Run resource,
  one more IAM binding, one more Docker image to build in CI — accepted because it's a concrete, explainable
  responsibility split, not scope-creep for its own sake.

## End-to-end question flow

1. React → `POST /api/chat`
2. FastAPI validates request, creates trace/session metadata
3. Gemini agent identifies intent/topic
4. Agent calls `search_knowledge()`
5. Query is embedded
6. Semantic vector retrieval returns candidates
7. Lexical search returns candidates
8. Results merged / deduplicated / reranked
9. Candidate `knowledge_id`s validated against BigQuery governance
10. Agent optionally calls source/metadata tools
11. Approved chunks + source metadata become grounding context
12. Gemini generates an educational response
13. FastAPI returns answer + sources + related topics
14. Interaction telemetry published to Pub/Sub
15. Dataflow processes events into BigQuery analytics
16. Admin console displays retrieval/agent/analytics information

## Agent tools

| Tool | Responsibility |
|---|---|
| `search_knowledge(query, topic)` | Run hybrid RAG, return governed knowledge candidates |
| `get_knowledge_record(knowledge_id)` | Retrieve structured semantic metadata |
| `get_source_metadata(source_id)` | Return source details and provenance |
| `check_content_eligibility(knowledge_id)` | Verify final governance eligibility |
| `query_health_topics()` | Retrieve available topics/categories |
| `find_related_topics(topic_id)` | Support related-topic presentation |

Single Gemini orchestrating agent, built with Google's Agent Development Kit (ADK) rather than a hand-rolled
function-calling loop — ADK's agent/tool abstractions match this exact "one agent, explicit tools" shape and its
built-in tracing covers a chunk of the Agent Observability phase for free. Do not add additional agents unless a
concrete later requirement justifies independent roles or a state machine.

## GCP services and their concrete responsibility

| Service | Use |
|---|---|
| Cloud Storage | Raw source files, unstructured content, quarantine data |
| Dataflow | Batch transformations and streaming event processing |
| BigQuery | Raw/curated/semantic data, governance authority, analytics |
| Pub/Sub | Streaming application events and ingestion signals |
| Vertex AI Gemini | Agent reasoning, tool calling, response generation |
| Vertex AI embeddings / vector retrieval | Semantic RAG retrieval |
| Cloud Run | Two services: FastAPI `backend` (public) and the ADK `agents` service (private, invoker-restricted to `backend`) |
| Cloud Functions | One small event-triggered ingestion responsibility |
| Artifact Registry | Container images |
| Secret Manager | Runtime secrets/configuration |
| IAM | Least-privilege service identities |
| Cloud Logging/Monitoring | Application/pipeline observability |
| Cloud Composer | Optional, post-MVP scheduled orchestration only |

Every deployed component must have a concrete responsibility above — do not add services solely to match a job
description.

## Decision log

Record deviations from the source plan here as they happen, with rationale and date.

- _2026-09-21_ — Repository scaffolding created; no architectural deviations yet.
- _2026-09-21_ — Agent runtime moved out of `backend/src/agents/` to a root-level `agents/` directory, built on
  Google ADK, deployed as its own private Cloud Run service rather than living inside the FastAPI process. See
  "Service topology" above for the resulting shape and rationale. Deviates from the plan's single-Cloud-Run-box
  diagram; kept BigQuery-as-governance-authority and controlled-tool-access principles unchanged.
