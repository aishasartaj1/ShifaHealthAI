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
React/Vite UI  ── Cloud Run service "frontend", public
     |
     v  POST /api/chat, GET /api/topics, /api/admin/*   (public)
FastAPI backend  ── Cloud Run service "backend", public
     |
     v  ID-token-authenticated call (backend's SA is the only roles/run.invoker on agents)
ADK agent service ── Cloud Run service "agents", public network ingress, IAM-gated
     |
     v
Vertex AI Gemini + retrieval/governance tools
```

All three are public-network-reachable (`INGRESS_TRAFFIC_ALL`) — "private" for `agents` means
**IAM-gated, not network-isolated**: `allow_unauthenticated = false`, with only `backend`'s service account
granted `roles/run.invoker`, scoped to that one service, not project-wide. Deploying an actual
`INGRESS_TRAFFIC_INTERNAL_ONLY` restriction was tried first and found (by deploying and testing, not anticipated
in advance) to require a Serverless VPC Access connector for Cloud-Run-to-Cloud-Run calls to work at all —
without one, it silently blocks every caller, including `backend` itself. See the 2026-09-21 (Phase 8)
decision-log entry. Identity-based (zero-trust) auth without network isolation is also simply the more common
production pattern for this kind of service-to-service call — not a compromise made for this project's sake.

- `backend/` — FastAPI. Public entrypoint for the frontend. Owns everything that *isn't* agent reasoning:
  topics/sources/knowledge lookups, admin/governance/analytics endpoints, request validation, session/trace
  bookkeeping, forwarding chat requests to the agent service and returning its response.
- `agents/` — a standalone [Google ADK](https://google.github.io/adk-docs/) application. Owns the orchestrating
  Gemini agent and its tools (`search_knowledge`, `get_knowledge_record`, `get_source_metadata`,
  `check_content_eligibility`, `query_health_topics`, `find_related_topics`). Deployed as its own Cloud Run
  service; only `backend`'s service account can actually invoke it.
- Why split them: mirrors how ADK is meant to run (as its own agent runtime, not embedded inline in an arbitrary
  web framework), gives a real IAM-enforced trust boundary to point to ("the web tier cannot reach Gemini or the
  retrieval tools directly — only the agent service can, and only the backend can reach the agent service"), and
  keeps agent code deployable/scalable independently of the web-serving code. Cost: one more Cloud Run resource,
  one more IAM binding, one more Docker image to build in CI — accepted because it's a concrete, explainable
  responsibility split, not scope-creep for its own sake.

### The two HTTP relationships between backend and agents

There are two, in opposite directions, for two different reasons — and, as of Phase 8, **both are protected the
same way**: a Google-issued ID token, minted by the caller's own Cloud Run service-account identity
(`google.oauth2.id_token.fetch_id_token`, audience = the callee's URL) and verified by the callee
(`google.oauth2.id_token.verify_oauth2_token`, checking both signature and the caller's `email` claim).

1. **`backend -> agents`**, for the chat flow: `backend/src/services/agent_client.py` calls `agents`' `POST
   /invoke` to run the Gemini agent for a user message. Protected by the `roles/run.invoker` binding — Cloud Run
   itself rejects an unauthenticated or wrongly-authenticated call before it ever reaches `agents`' application
   code (confirmed directly: an unauthenticated call gets a `403` from Cloud Run's own edge).
2. **`agents -> backend`**, for the agent's tools: each of the six tools (`agents/src/tools.py`) is a plain HTTP
   call into `backend`'s `/internal/*` API (`backend/src/api/internal.py`), which wraps
   `backend/src/repositories/bigquery.py` and `backend/src/retrieval/search.py`. `agents/` holds no BigQuery or
   Vertex-AI-embeddings credentials of its own — every retrieval/lookup call it makes is really backend doing the
   work on its behalf. This is what "Controlled agent access" (the principles table above) means concretely: the
   agent's only path to data is through these six HTTP calls, not a raw table or a shared library import.
   `backend` has public ingress (the frontend needs to reach it), so there's no Cloud-Run-level IAM boundary the
   way there is for (1) — `backend` verifies the token itself, at the application layer
   (`_verify_id_token` in `internal.py`), checking the token's audience against `backend`'s own public URL and
   its `email` claim against `agents`' service account.

   Both directions keep a shared-secret header (`X-Internal-Api-Key`, from Secret Manager, not a hardcoded
   value) as a fallback for local development, where a human's ADC credentials can't mint a service-account ID
   token — `fetch_id_token` is skipped entirely when `environment == "dev"` rather than attempted and caught,
   since discovering that ADC can't mint one takes several real seconds per call otherwise.

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
| Cloud Run | Three services, all live: FastAPI `backend` (public), the ADK `agents` service (public network ingress, invoker-restricted to `backend` via IAM), and `frontend` (static SPA, public) |
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
- _2026-09-21_ (Phase 5) — Built `agents/`'s six tools as HTTP calls into a new `backend/src/api/internal.py`,
  confirming the "agent calls backend via HTTP" side of the split decided above. Auth on that internal API is a
  shared-secret header, a known-temporary simplification (see "The two HTTP relationships" above) — flagged as a
  Phase 8 follow-up, not silently left unresolved.
- _2026-09-21_ (Phase 6) — Added `GET /api/topics/{topic_id}/knowledge`, not in the plan's original Section 19
  API list, because the topic explorer (`Topics.tsx`) needed a way to actually show a topic's records once
  selected. Agent trace capture (`agents/src/trace.py`) was widened to record `knowledge_id`s alongside candidate
  counts, not just counts — `POST /api/chat` needs the actual IDs to build source cards, and an ID is a
  structured reference, not raw content, so this doesn't compromise "no raw chain-of-thought." `GET
  /api/admin/agents`/`{trace_id}` reads from a bounded, process-local, in-memory store
  (`backend/src/services/trace_store.py`) — see the Phase 7 entry below for why this stays in-memory rather
  than being folded into that phase's streaming work.
- _2026-09-21_ (Phase 7) — `QUESTION_ASKED`/`RESPONSE_GENERATED` are published server-side by
  `backend/src/api/chat.py`; `SOURCE_OPENED`/`RELATED_TOPIC_OPENED`/`FEEDBACK_SUBMITTED` are published by a new
  `POST /api/events` on the frontend's behalf — a deliberate split, not an oversight: only `chat.py` reliably
  knows the first two genuinely happened, so accepting them from the client would let one be fabricated.
  `pipelines/streaming/` quarantines invalid events into a BigQuery table (`curated.quarantined_events`), not a
  GCS file the way batch's pipeline does — an unbounded Pub/Sub-sourced streaming pipeline needs
  window/trigger finalization to ever flush a file sink, which is real added complexity for no benefit at this
  event volume; a streaming insert needs none of that. `semantic.question_analytics` is populated by a small
  re-runnable script (`scripts/refresh_analytics.py`), not continuous Beam-windowed aggregation, for the same
  "simplest defensible option at this scale" reasoning used throughout this project. Note this phase did **not**
  migrate `backend/src/services/trace_store.py` (agent traces) to durable storage — it built durable storage for
  *interaction events* only; agent-trace persistence is a separate, still-open concern if it's ever needed.
- _2026-09-21_ (Phase 8) — Deployed all three services live. `agents`' ingress is `INGRESS_TRAFFIC_ALL`, not
  `INGRESS_TRAFFIC_INTERNAL_ONLY` as originally planned — internal-only Cloud-Run-to-Cloud-Run calls need a
  Serverless VPC Access connector, discovered by deploying with `INTERNAL_ONLY` and finding that *no* caller
  (including `backend`, including a manually-authorized human identity used to isolate the bug) could reach it.
  IAM (`roles/run.invoker`, scoped to `backend`'s service account on that one service) is the real trust
  boundary instead — see "The two HTTP relationships" above. Real ID-token verification (Phase 5's ticketed
  follow-up) is implemented in both `backend -> agents` and `agents -> backend` directions, with the
  shared-secret header kept only as a local-dev fallback (skipped entirely, not attempted-then-caught, when
  `environment == "dev"` — a real several-seconds-per-call cost otherwise). `backend`/`agents`/`frontend` each
  need one of the *other two* services' real URLs in their config; direct Terraform module-output references
  between `backend` and `agents` would be a genuine circular dependency, so both are derived instead from
  `var.cloud_run_url_suffix` — a value that had to be corrected once already, since the first guess at Cloud
  Run's default URL format (project-number-based) was wrong; the real format is an opaque per-project+region
  hash, confirmed against the actual `.uri` output.
- _2026-09-21_ (Phase 9) — CI/CD added via `infra/terraform/modules/cicd/` (Workload Identity Federation, no
  service-account JSON keys) and two GitHub Actions workflows (`pr.yml`, `deploy.yml`). The CI service account is
  deliberately denied any `terraform apply`-level role — it can push images, trigger Cloud Build, and deploy new
  revisions to the 3 existing Cloud Run services (`run.developer`, not `run.admin`), plus read-only roles so
  `terraform plan` works in PRs. `deploy.yml` never calls `terraform apply`; infra changes stay a manual,
  reviewed step. One accepted consequence: Terraform's Cloud Run modules still declare `image = ".../*:latest"`
  as the provisioned image, while `deploy.yml` deploys SHA-tagged images going forward — the two are allowed to
  disagree on image tag (Terraform owns service configuration, CI owns which image is currently running); a
  future `terraform apply` touching those modules would reset the running image back to `:latest`, acceptable
  for now since it hasn't caused a real problem.
- _2026-09-22_ — Built `functions/` (deferred from Phase 8): one Eventarc-triggered Cloud Function on the `raw`
  bucket's `object.finalized` event, publishing a structured signal to its own Pub/Sub topic
  (`shifahealth-ingestion-signals`) and nothing else — no downstream consumer, per Section 17's "demonstrates
  event integration without moving core business logic out of the main pipeline." Its own Terraform module
  (`infra/terraform/modules/functions/`) needed two service-account grants beyond the obvious
  `pubsub.publisher`-for-the-GCS-service-agent one every quickstart mentions: `roles/eventarc.eventReceiver` for
  the trigger's own service account, and `roles/storage.objectViewer` scoped to the `raw` bucket so that same
  service account can pass Eventarc's `storage.buckets.get` validation check at trigger-creation time — the
  second of the two was found only by actually running `terraform apply`, not from any setup guide. Verified
  end-to-end (real file upload, real Pub/Sub pull, real cleanup), not just a successful `apply`.
