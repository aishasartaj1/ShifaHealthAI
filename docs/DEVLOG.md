# Development Log

A chronological build journal for ShifaHealth AI — kept for two reasons: so this project can be picked back up
and understood later, and so it doubles as interview prep ("walk me through how you built this").

Unlike [architecture.md](architecture.md) (which describes the system as it currently stands) and
[BACKLOG.md](BACKLOG.md) (which tracks what's left), this file records **how we got there**: what was built, why
that choice was made over the alternatives, where we deviated from the original plan and why, and what's worth
being able to explain out loud about it.

Format per entry: date, what happened, why, deviations (if any), interview notes (if any).

---

## 2026-09-21 — Repository scaffolding, backlog, GitHub remote, GCP project

**What:** Initialized the git repo and created the full directory layout from the architecture plan's Section 27
(`frontend/`, `backend/`, `pipelines/`, `functions/`, `data/`, `infra/terraform/`, `scripts/`, `docs/`,
`.github/workflows/`). Seeded `docs/` with `architecture.md`, `data-model.md`, `governance.md`, `rag-design.md`,
`demo-script.md`, and `BACKLOG.md` (the phase-by-phase implementation backlog derived from the plan's Sections
27–30: repo structure, MVP definition, 10-phase sequence, deferred-scope list). Made the root commit, then added
`https://github.com/aishasartaj1/ShifaHealthAI` as the `origin` remote, renamed the local branch `master` → `main`
to match GitHub's default, and pushed.

Separately, created the GCP project for this work: name `ShifaHealthAI`, project ID `shifahealthai`, no
organization (personal/portfolio account, so "No organization" is correct — there's no Google Workspace org to
attach it to).

**Why:**
- Structure and backlog came straight from the plan document rather than being designed fresh — the plan is the
  source of truth, this repo is its implementation.
- Empty directories needed `.gitkeep` files since git doesn't track empty dirs.
- `main` instead of `master` to match the GitHub remote's default branch and avoid a mismatch on first push.
- GCP project has no organization because this is a personal portfolio project, not a company's Workspace/Cloud
  Identity setup. That also means IAM has no org-level policy to inherit from — everything is project-level.

**Deviations from the plan:** None yet. This was pure scaffolding.

**Interview notes:**
- Be able to explain *why* the repo is organized as raw → curated → semantic (see `data-model.md`) before writing
  any code — it's a deliberate governance decision, not incidental structure.
- GCP project IDs are **globally unique and immutable once created** (`shifahealthai` can't be changed or reused
  elsewhere) — worth knowing why the console warns about that before you click Create.
- The plan explicitly separates infra provisioning (Terraform) from app deployment (GitHub Actions build/deploy) —
  that separation is intentional and should show up in the CI/CD phase, not be an afterthought.

---

## 2026-09-21 — Phase 1 foundation: backend, frontend, Terraform base; agent runtime moved to its own service

**What:** Built out Phase 1 of the backlog:
- `backend/`: FastAPI skeleton (`src/main.py`, `src/config/settings.py` via `pydantic-settings`), a `/health`
  route, `requirements.txt`/`requirements-dev.txt`, `.env.example`, and a passing test (`tests/test_health.py`)
  verified with `pytest` and a live `uvicorn` boot.
- `frontend/`: scaffolded fresh with `npm create vite@latest -- --template react-ts` (this **replaced** the
  manually-created placeholder folders from the initial scaffold — Vite generates its own `src/`), then added
  `react-router-dom` and rebuilt `src/pages/{Assistant,Topics,AdminOverview}.tsx` with a router shell in `App.tsx`
  for `/`, `/topics`, `/admin`. Verified with `npm run build` (type-checks + bundles clean) and a dev-server boot.
- `infra/terraform/environments/dev/`: provider config pinned to `hashicorp/google ~> 6.0`, a **local** Terraform
  backend (state file on disk, not GCS — see "Why" below), and a `google_project_service` resource enabling the
  13 APIs the whole backlog needs (Cloud Run, BigQuery, Pub/Sub, Dataflow, Vertex AI, Artifact Registry, Cloud
  Functions, Cloud Build, Secret Manager, IAM, Storage, Logging, Monitoring). `terraform init` succeeded against
  the `shifahealthai` project.

**Why:**
- Frontend was rebuilt via the official Vite CLI instead of hand-writing config, because a scaffolding tool gets
  the TypeScript/Vite/ESLint wiring right in ways worth not re-deriving by hand.
- Local Terraform backend chosen over a GCS backend for now: a GCS backend needs a bucket to already exist, and
  having Terraform manage the very bucket it stores its state in is a bootstrapping problem. Fine for a
  single-contributor DEV portfolio project; flagged in `backend.tf` as the thing to revisit if this ever needs
  multiple contributors.
- APIs are enabled via `google_project_service` in Terraform, not by clicking through the console or running ad
  hoc `gcloud services enable` — keeps "what's turned on in this project" declarative and reviewable in a diff,
  consistent with the plan's "Terraform is mandatory" stance.

**Deviations from the plan (this is the big one):**

The plan's Section 19 put agent code inside `backend/src/agents/`, run in the same FastAPI process as the rest of
the backend (implied by the single "FastAPI (Cloud Run)" box in the architecture diagram). Over the course of
this session we changed that twice:

1. First cut: agent code was removed from `backend/src/agents/` entirely (it was still just an empty
   `.gitkeep` placeholder — Phase 5 hadn't started) rather than leaving a premature empty directory in place.
2. Then: decided the agent runtime should be a root-level `agents/` directory, sibling to `backend/` and
   `frontend/` — not nested inside the backend at all.
3. Then: decided *why* it should be root-level — we're building it on **Google's Agent Development Kit (ADK)**
   rather than hand-rolled Gemini function-calling, and ADK's natural deployment shape is its own agent runtime,
   not inline code in an arbitrary web framework. Root-level `agents/` reflects that it's a separate deployable,
   not a backend module.
4. That led to the real architectural fork: does `agents/` run *inside* the backend process (imported as a
   library) or as its *own* Cloud Run service? Chose **its own service** — see `architecture.md`'s new "Service
   topology" section. `backend` (FastAPI, public ingress) becomes the only public entrypoint and everything
   else's owner (topics/sources/admin/governance/analytics endpoints); `agents` (ADK, private ingress) owns the
   Gemini orchestrator and its six tools, reachable only from `backend` via an IAM `roles/run.invoker` binding
   scoped to that one service, not project-wide.

This is a deliberate deviation from the plan's diagram, not an accident — recorded in `architecture.md`'s decision
log the same day. `BACKLOG.md`'s Phase 5 and Phase 8 tickets were rewritten to match (two `cloud_run` module
instantiations instead of one, an agents-specific IAM binding, an open question flagged for later: whether the
agent's tools call back into `backend` over HTTP or share a retrieval library directly).

**Interview notes:**
- Be ready to explain the backend/agents split as an IAM-enforced trust boundary, not just a folder choice: "the
  web tier can't reach Gemini or the retrieval tools directly — only the agent service can, and only the backend
  can invoke the agent service." That's a real, demonstrable security property (`roles/run.invoker` scoped to one
  service, not the whole project), not decoration.
- Be ready to justify the cost: one more Cloud Run service, one more IAM binding, one more container image in
  CI, one more network hop for every chat request. The plan says "don't add services solely to match a job
  description" — the honest answer for why this one clears that bar is the trust-boundary property above, plus
  ADK's deployment model expecting to run standalone. If asked "would you do this for a real production system
  with tighter latency requirements?", the honest answer is: it depends on whether the extra hop's latency cost
  is worth the isolation — worth having a real opinion on this rather than just defending the choice reflexively.
- Know what ADK actually buys over hand-written function-calling: agent/tool abstractions matching this exact
  "one agent, explicit tools" shape, and built-in tracing/session handling that offsets some of the Agent
  Observability phase's custom-code needs. It's a framework choice, not a requirement of the plan — the plan
  never mandates ADK, only "a Gemini agent... using controlled tools."
- `terraform init` succeeding is not the same as `apply` having run — no real GCP resources exist yet from this
  config. Don't accidentally claim more infrastructure exists than actually does.

**Update — same day:** ran `terraform plan` (13 `google_project_service.required` resources, 0 changes/destroys —
reviewed before applying since it touches the real `shifahealthai` project), then `terraform apply`. All 13 APIs
are now enabled on the project. Also caught and fixed a mistake in `.gitignore`: `.terraform.lock.hcl` was listed
under the Terraform ignore block, which is backwards — that lock file pins exact provider versions and is
supposed to be committed (only `.terraform/`, `*.tfstate`, and `terraform.tfvars` should be ignored). Phase 1 is
now fully done; backlog's "Next action" points at Phase 2 (data model / seed data).

---

## 2026-09-21 — Phase 2: seed data, `bigquery` Terraform module, load into BigQuery

**What:** Authored the seed dataset and loaded it into the real `shifahealthai` project:
- 6 topics (`data/seed/health_topics.csv`): menstrual cycles, PCOS, menopause, contraception, pregnancy
  education, cervical health/screening — one from each of the plan's Section 3 domain branches that had
  reasonably self-contained public source material.
- 9 sources (`sources.csv`), each a **real, verified-via-web-search** public-health page — Office on Women's
  Health, ACOG, NIA/NIH, CDC, MedlinePlus — with the actual title and URL, not guessed ones.
- 38 knowledge records (`knowledge_metadata.csv`), each a short educational summary **paraphrased in my own
  words** from what the source search results returned, not copy-pasted — plus governance fields
  (`review_status`, `content_status`, `published_date`, `last_reviewed_date`, `content_version`).
- 38 matching review rows (`medical_reviews.csv`) with synthetic reviewer role labels (e.g. "OB/GYN Reviewer
  (Synthetic)") — explicitly fake reviewer identities, since real named reviewers would misrepresent who
  actually touched this content.
- `safety_rules.json`: agent-side config (disclaimer text, out-of-scope intents, escalation keywords for
  self-harm/emergency situations) — authored now per the plan's file list, consumed later in Phase 5.
- `infra/terraform/modules/bigquery/`: `raw`/`curated`/`semantic` datasets, and the 4 `raw` tables with JSON
  schema files matching the CSVs. Wired into the dev environment as a module, planned, and applied — verified
  with `bq ls` that the datasets/tables exist on the real project.
- `scripts/validate_seed_data.py` (+ a pytest wrapper): stdlib-only schema/enum/foreign-key/date validation over
  the CSVs, run before any load.
- `scripts/seed_bigquery.py`: validates, then loads each CSV into its `raw.*` table with `WRITE_TRUNCATE` (safe
  to re-run after editing seed data). Ran it for real; verified row counts and the governance-status distribution
  with `bq query`.

**Why:**
- Sources were found via `WebSearch` rather than recalled from memory or guessed, specifically to avoid citing a
  URL that doesn't exist or misattributing content to the wrong org — both would undermine the entire point of
  a "governed" knowledge platform.
- Summaries are paraphrased, not copied, because the plan explicitly says not to present scraped third-party text
  as proprietary content, and because verbatim reproduction of another org's page text raises copyright concerns
  a portfolio project doesn't need to take on.
- **Five records were deliberately seeded as governance failures** (2 `STALE`, 1 `EXPIRED`, 2 `NEEDS_REVIEW`) —
  spread across different topics rather than clustered in one, and assigned independently of whether the real
  source page is actually still active (all 9 real sources are, in fact, live and current — the fictional part is
  our *internal* review workflow status, not a claim about the external org's page). Without this, every later
  governance/eligibility demo (Phase 4's query-time filter, the admin console's governance view, the
  data-quality "AI eligibility %" metric) would have nothing real to show — a pipeline that always approves
  everything doesn't prove the governance layer does anything.
- `ai_eligible` stayed out of the raw schema on purpose (see the Phase 1 entry above where this was first
  decided) — it's `review_status==APPROVED AND source_status==ACTIVE AND content_status==CURRENT`, and that
  computation belongs to Phase 3's Dataflow job, not to hand-authored seed data. `validate_seed_data.py` prints a
  preview count (33/38 eligible) so a badly-skewed seed set would be caught now, but it does not write that flag
  anywhere.
- Only `raw.*` tables got schemas in Terraform. `curated.*`/`semantic.*` are datasets-only for now; defining their
  table schemas before Phase 3's transform logic exists would mean designing the dimensional model backwards
  from a guess instead of from the actual join/aggregation logic.
- Hit a real permissions snag applying `seed_bigquery.py`: the `google-cloud-bigquery` Python client used the
  ADC "quota project" for billing/permission checks, which was still set to an unrelated project
  (`bq-verse-sandbox-052025`) from prior work on this machine — even though `bigquery.Client(project=...)` was
  correctly pointed at `shifahealthai`. Fixed with `gcloud auth application-default set-quota-project
  shifahealthai`, which only edits the local ADC credentials file, not the gcloud CLI's active project config
  (a different, unrelated setting) — so it didn't disturb whatever project other gcloud work on this machine
  is using.

**Deviations from the plan:** None beyond the agents/service-topology one already logged in `architecture.md`.
Phase 2's scope (raw tables + seed load only, curated/semantic schemas deferred) is a scoping choice within the
plan, not a deviation from it — the plan doesn't specify when each layer's schema gets written, only that all
three layers exist by the MVP.

**Interview notes:**
- Be able to name the actual sources cited (Office on Women's Health, ACOG, NIA/NIH, CDC, MedlinePlus) and why
  they were chosen (all US federal or major professional-medical-org sources, appropriate for general
  educational content — not needed to be exhaustive, needed to be credible).
- Be ready to explain *why* 5 records are deliberately non-eligible and point to exactly which ones and why
  (`know_mc_007`, `know_pcos_006`, `know_meno_006`, `know_preg_006`, `know_cerv_006`) — this is the kind of detail
  that separates "I understand governance" from "I can recite the word governance."
- `ai_eligible` not existing yet is a feature of the current state, not a bug — but know where it will live
  before it's asked as a caught-out question: computed in Phase 3, written to `semantic.agent_eligible_knowledge`,
  re-validated again at query time per `docs/governance.md`'s "Enforcement points."
- ADC quota project vs. gcloud CLI active project are two different pieces of local state that can silently
  disagree — worth understanding the difference rather than memorizing the fix command.

---
