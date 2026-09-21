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

## 2026-09-21 — Phase 3: Beam batch pipeline, curated/semantic tables populated for real

**What:** Built `pipelines/batch/` as three layers — `transforms.py` (pure Python, no Beam import: every
validation rule, the dedup policy, and `compute_ai_eligible`, all unit-tested with plain dicts), `pipeline.py`
(the actual Beam DAG: dedup → validate → enrich → write, per table, wired with real side inputs), and `run.py`
(CLI). Extended the `bigquery` Terraform module with the 8 curated/semantic table schemas that Phase 2 deferred,
and added a new `storage` module for the `raw` and `quarantine` GCS buckets. Applied both, then ran the pipeline
for real against `shifahealthai` on Beam's `DirectRunner`.

**The DAG, in order:** read all 4 `raw.*` tables → dedup each by its ID field (`GroupByKey` + a `DoFn`; if more
than one row shares an ID, ALL copies get quarantined — no silently-picked "winner") → validate topics/sources
first (no FK dependencies) → build `topics_by_id`/`sources_by_id` side-input dicts from only the rows that passed
→ validate + enrich knowledge against those dicts (this is where `ai_eligible` finally gets computed, and where
`topic_name`/`source_name` get denormalized in) → build a `knowledge_by_id` dict from the enriched result →
validate reviews against it. Every rejected row, from any stage, gets tagged with its source table and reason and
flows into one `Flatten` → JSON-lines → GCS quarantine sink. Valid rows get written to `curated.*` (plain
validated/typed data) and `semantic.*` (`knowledge_catalog` = everything valid with denormalized names;
`approved_knowledge` = filtered to `review_status==APPROVED`; `agent_eligible_knowledge` = filtered to
`ai_eligible==true`, projected down to just the 4 fields Phase 4's chunking needs; `topic_knowledge_summary` = a
`GroupByKey` on `topic_id` with per-status counts).

**Why:**
- Validation logic lives in plain functions, not Beam `DoFn`s, specifically so `pytest` could test 21 cases (every
  required-field, enum, and FK failure mode, plus the `ai_eligible` truth table) in milliseconds with no Beam
  runner, no BigQuery, no GCS — Beam's own `TestPipeline` machinery would have made the same tests much slower to
  write and run for no extra coverage, since the DAG wiring itself is thin enough to verify by actually running it.
- Ran on `DirectRunner`, not submitted to managed Dataflow — 91 total rows across 4 tables doesn't justify
  spinning up Dataflow workers, and the code is runner-agnostic (`run.py --runner DataflowRunner` would submit
  the identical pipeline for real if the data volume ever justified it).
- Quarantining ALL copies of a duplicate ID (not just "extra" copies past the first) is the same reasoning as
  Phase 2's seed-data validator: there's no principled way to know which duplicate is "correct" without a human
  looking at it, so the pipeline refuses to guess.
- `curated.*` keeps `ai_eligible` as a plain boolean column but does NOT carry `topic_name`/`source_name` —
  those denormalized display fields belong in the semantic layer (which is what the API/agent actually read),
  not in a dimensional table whose job is to stay normalized.
- `fact_user_question` and `semantic.question_analytics` were **not** built, on purpose — nothing produces that
  data until Phase 7 (streaming events), so a table for it now would just be an empty, unexplainable shell.

**Bugs hit and fixed while actually running this against real BigQuery** (the value of not just writing this
against mocks):
1. `WriteToBigQuery` with `method=STREAMING_INSERTS` **rejects `WRITE_TRUNCATE`** — the streaming insert API has
   no way to truncate first. Fixed by truncating all 8 output tables via a plain `bigquery.Client` call
   (`TRUNCATE TABLE`) immediately before the Beam pipeline runs, then using `WRITE_APPEND` inside it. Net effect
   is identical (full-refresh-per-run), just split into two explicit steps instead of one disposition flag —
   worth knowing this is a real BigQuery/Beam constraint, not a bug in the pipeline design.
2. `ReadFromBigQuery` hands back `DATE` columns as native `datetime.date` objects, not ISO strings. My first
   version of `_parse_date` in `transforms.py` only handled strings — it would have rejected every single
   knowledge row as "unparseable date" the moment this ran against real data, even though every unit test
   (which used string dates directly) passed. Caught this **before** the first real run by reasoning about what
   the BigQuery client actually returns, not by it failing — added a regression test
   (`test_validate_knowledge_accepts_native_date_objects`) to lock it in.
3. The quarantine JSON serialization step (`json.dumps` on a quarantined row) hit the *same* `date`-object issue
   from a different angle: a quarantined row's raw fields — including `published_date`/`last_reviewed_date` —
   are native `date` objects, and `json.dumps` doesn't know how to serialize those by default. This one **did**
   fail on the first real run (deliberately triggered — see below), with `TypeError: Object of type date is not
   JSON serializable`. Fixed with a `default=` handler on `json.dumps` that calls `.isoformat()` on any `date`.
4. Two Beam `RuntimeError`s from duplicate transform labels (`_as_dict_by` called three times, each building an
   anonymous `beam.Map` with the same auto-generated label) — fixed by passing an explicit label string to every
   reused helper. Straightforward once seen, but a reminder that Beam requires every step in a pipeline to have a
   unique name, generated ones included.

**Verified, not just asserted:** ran `bq query` after each pipeline run rather than trusting "pipeline done!" —
row counts matched exactly (6/9/38/38 curated, 38/35/33/6 semantic) on the clean run. Then deliberately inserted
one row into `raw.raw_knowledge` with a nonexistent `topic_id`, re-ran, and confirmed via `gsutil cat` that it
landed in the quarantine JSONL with reason `"unknown topic_id 'nonexistent_topic'"`, while `curated.dim_knowledge`
and `semantic.agent_eligible_knowledge` counts stayed exactly the same (the bad row did not leak through). Then
deleted the test row and re-ran to restore the clean state. This is the same instinct as Phase 2's deliberately-
seeded governance failures: don't just build a pipeline that always accepts everything and call it "governed" —
prove the rejection path actually rejects something.

**Deviations from the plan:** None beyond what's already logged (the `agents/` service split). Building
curated/semantic schemas now, rather than in Phase 2, was the planned sequencing, not a new deviation.

**Interview notes:**
- Be able to walk through the DAG's dependency order from memory: why topics/sources validate first, why
  knowledge's side inputs come from validated topics/sources rather than raw ones, why reviews depend on enriched
  knowledge rather than raw knowledge. This ordering is the actual enforcement of referential integrity, not
  decoration.
- Know the STREAMING_INSERTS + WRITE_TRUNCATE incompatibility cold — it's a very findable "have you actually run
  this" question, and the fix (truncate-then-append) is a real, defensible pattern, not a workaround to be
  embarrassed about.
- Be ready to explain why `DirectRunner` was the right call here and what would change the answer (data volume,
  latency requirements, need for autoscaling/retries that only a managed runner provides).
- The quarantine JSON bug is a good "tell me about a bug you caught" story: found by deliberately trying to break
  the thing I'd just built, not by a user report.

---

## 2026-09-21 — Phase 4: hybrid retrieval, real embeddings, a real governance-drift test

**What:** Built `backend/src/retrieval/` — `semantic.py` (Vertex AI `text-embedding-005` via the `google-genai`
SDK + pure cosine similarity, no numpy), `lexical.py` (BM25 via `rank-bm25`), `hybrid.py` (min-max score
normalization + weighted merge/rerank, dedup by `knowledge_id`), `governance.py` (query-time eligibility
re-check), and `search.py` (`search_knowledge()`, the composed entrypoint matching rag-design.md's diagram:
semantic + lexical → merge/dedupe/rerank → governance filter → top governed candidates). Added
`scripts/build_index.py`, the offline indexing step: reads `semantic.agent_eligible_knowledge`, embeds each
summary, writes `semantic.knowledge_embeddings` (a new BigQuery table, extended into the `bigquery` Terraform
module and applied). Ran it for real — 33 rows, 768-dim vectors each.

**Why these specific choices:**
- **Vector store is BigQuery, not Vertex AI Vector Search / Matching Engine.** At 33 rows, brute-force cosine
  similarity in Python is microseconds — standing up a separate managed vector service would be pure ongoing
  cost with zero benefit, and it would also mean the vector data lives in a second system that could drift from
  the governance data it's derived from. This is the same "don't add a service without a concrete responsibility"
  reasoning as the `agents/` split, just landing on the opposite conclusion here. Revisit if the corpus ever
  grows past what brute-force scanning can handle.
- **Chunking is a no-op.** Every knowledge summary is already one short paragraph — there's nothing to split.
  `chunk_id == knowledge_id`. This would need real sliding-window chunking the day source documents stop being
  short synthetic summaries and become actual multi-paragraph articles.
- **`google-genai` over the older `vertexai` SDK**, since `agents/` (Phase 5) will need a Gemini client either
  way and using one SDK for both embeddings and generation avoids carrying two Google AI client libraries.
- **BM25's lexical corpus is fetched fresh from BigQuery on every call**, not materialized into its own index
  table the way embeddings are. There's no expensive step to justify caching it (unlike embedding, which costs an
  API call per row), so there's no lexical-side staleness to worry about — only the embeddings table can drift
  from BigQuery's live governance state, which is exactly why the governance filter step still earns its place
  even though the index is pre-filtered at build time.
- **`search_knowledge()` asks for `top_n * 2` candidates before governance-filtering down to `top_n`** — otherwise
  a query that happens to surface a couple of now-ineligible candidates would silently return fewer results than
  asked for instead of backfilling from the next-best eligible ones.

**The governance-drift test (the part worth remembering):** pre-filtering the index at build time
(`agent_eligible_knowledge`, per rag-design.md's own spec) means that on a *freshly built* index, the governance
filter has nothing to reject — every candidate is already eligible by construction. That's not the same as
proving the filter *works*. So: queried `semantic_search()` alone for "What are common PCOS symptoms" — top
match, `know_pcos_002`, score 0.839. Then deleted `know_pcos_002` from `semantic.agent_eligible_knowledge` only
(NOT from `knowledge_embeddings`), simulating exactly the scenario docs/governance.md's "Enforcement points" #3
describes: a record was eligible when indexed, and isn't anymore by query time. Re-ran the full
`search_knowledge()` — `know_pcos_002` was completely absent from the governed results, even though
`semantic_search()` alone (re-run at the same moment) still returned it as the top match. Restored by re-running
the Phase 3 batch pipeline (which fully repopulates `agent_eligible_knowledge` from `curated.dim_knowledge`,
where the row's `ai_eligible` flag was never touched).

**Deviations from the plan:** None. `search_knowledge()`'s shape matches rag-design.md's diagram directly.

**Interview notes:**
- Be ready to explain *why* the vector index is built from `agent_eligible_knowledge` (pre-filtered) rather than
  the full `knowledge_catalog`, since it's genuinely arguable either way — the plan's own Section 11.1 spec says
  pre-filtered, and the governance filter's job is to catch drift between build-time and query-time, not to do
  the primary filtering. I considered switching to the broader catalog specifically so governance would have
  more to reject, then realized that would be solving a testing-convenience problem by changing production
  design — the drift test above is the honest way to prove the same thing without that.
- Know the asymmetry between lexical (always fresh, queries BigQuery every call) and semantic (can go stale,
  depends on `build_index.py` having been re-run) — and be able to say which one the governance filter is really
  protecting against.
- `search_knowledge()` itself isn't unit tested — only its pieces are. That's a deliberate choice (it's IO
  composition, not logic), verified instead by actually running it against real data, the same pattern as every
  prior phase.

---

## 2026-09-21 — Phase 5: the ADK agent, a real internal API, and a real session-persistence bug

**What:** Built `agents/` as a standalone Google ADK service and `backend/src/api/internal.py` as its data-access
backend, then proved the whole thing end-to-end against live Vertex AI Gemini — not mocked.

- `agents/src/tools.py`: all six tools from the plan's Section 12, each a plain function (ADK derives the
  function-calling schema from the type hints + docstring) that makes an `httpx` call into one of six new
  `backend` endpoints under `/internal/*`.
- `backend/src/api/internal.py` + `backend/src/repositories/bigquery.py`: those six endpoints. `search-knowledge`
  wraps Phase 4's `search_knowledge()`; the rest are small parameterized BigQuery lookups (`get_knowledge_record`,
  `get_source_metadata`, `check_content_eligibility`, `query_health_topics`, `find_related_topics`).
  `find_related_topics` uses the simplest defensible heuristic available — other topics sharing the same
  `parent_category` (e.g. PCOS → Menopause, both "Hormonal Health"), falling back to any other topic if none
  share a category — since there's no topic-relatedness data to score against yet.
- `agents/src/agent.py`: one `LlmAgent`, model `gemini-2.5-flash` via Vertex AI, an instruction that pins it to
  educational-only answers grounded in `search_knowledge`'s results, explicit refusal language for
  diagnosis/treatment/medication questions, and a line telling it to trust its own session's conversation history
  (see the memory bug below for why that line exists).
- `agents/src/trace.py` + `agents/src/main.py`: tool-call observability (tool name, args, a small result summary,
  latency — never the model's own reasoning text) via ADK's `before_tool_callback`/`after_tool_callback`, and a
  FastAPI wrapper (`POST /invoke`, `GET /health`) since ADK itself doesn't ship an HTTP server meant for this use.
- `backend/src/services/agent_client.py`: backend's HTTP client for calling `agents`. Not wired to a public route
  yet (`POST /api/chat` is Phase 6) — Phase 5's job was proving the agent itself works, which it now demonstrably
  does, independent of whether anything public calls it yet.

**Confirmed with a real smoke test before writing anything else:** before designing any of the above, ran a
throwaway ADK agent with one dummy tool against live Vertex AI Gemini (`gemini-2.5-flash`) and watched a real
function-call → function-response → grounded-text-response cycle happen. Only started building the real thing
once that worked.

**Why these specific choices:**
- **Tools call backend over HTTP; `agents/` holds no BigQuery/Vertex-AI-embeddings credentials.** This was the
  open design question from Phase 1's service-topology decision, now actually resolved: it keeps "controlled
  agent access" (a stated principle) concrete and checkable — the agent's only path to data is these six HTTP
  calls, not a shared library, not direct table access.
- **`/internal/*` auth is a shared-secret header, not the same IAM mechanism protecting `backend -> agents`.**
  `backend` needs public Cloud Run ingress for the frontend, so there's no private-ingress IAM boundary to lean
  on the way there is for the agents service. Considered doing real Google ID-token verification now instead, but
  that adds a dev-vs-prod bypass-flag risk (a disabled-in-dev auth check left on by accident is a classic
  vulnerability) for a check that's moot anyway until Phase 8 actually deploys anything to Cloud Run. Logged as an
  explicit Phase 8 ticket rather than silently deferred.
- **Trace isolation uses `contextvars.ContextVar`, not a closure captured at agent-construction time.** The first
  design built a fresh `Agent` + `Runner` + `TraceRecorder` per request via closures — simple, but it turned out
  to be the root of the memory bug below. A `ContextVar` set at the top of each request handler is visible only
  within that request's `asyncio` Task, which is exactly the isolation a per-request trace needs without having
  to rebuild the agent every time.

**The real bug (this is the one worth remembering):** multi-turn memory didn't work on the first try — asking
"what was the first question I asked you in this session?" got "I don't have the ability to recall past
questions," even when reusing the same `session_id`. The actual root cause: `POST /invoke`'s first version built
a brand-new `InMemoryRunner` (and therefore a brand-new, empty `InMemorySessionService`) on *every single
request*. Reusing a `session_id` did nothing, because the storage that `session_id` was supposed to look up in
had just been thrown away and recreated. Fixed by making the `Runner` a module-level singleton, built once at
process start, with `ContextVar`-based trace isolation solving the "but I still need per-request state"
problem the closure approach used to solve.

After that fix, the *same* memory-sounding question still got refused. Before concluding the fix didn't work,
debugged one level deeper: wrote a standalone script using the exact same persistent-Runner pattern, and printed
the literal `contents` list going into the LLM request on the second turn. It contained the full first turn —
user message, the tool call, the tool response, and the model's answer — verbatim. Asking the model to "repeat
your previous answer word for word" in that same debug script worked perfectly. So the infrastructure was
correct; the specific phrasing "did you recall/remember" triggers a reflexive "I don't retain memory across
conversations" response in Gemini regardless of what's actually in context — a known-ish model behavior, not a
bug in this system. Added an instruction line telling the model it does have this session's history and should
stop disclaiming it; that reduced but didn't fully eliminate the phrasing sensitivity, which was an acceptable
place to stop rather than keep prompt-tuning around one specific way of asking.

**Deviations from the plan:** None beyond what's already logged. `find_related_topics`'s same-category heuristic
isn't specified anywhere in the plan (there's no topic-relatedness data source to derive it from yet) — noted as
a placeholder, not a hidden gap.

**Interview notes:**
- This is the strongest "tell me about a bug you found and how you debugged it" story in the project so far.
  The key move was refusing to trust the symptom ("it says it can't remember") and instead checking the actual
  request payload going to the model — which is what separated "the session logic is broken" (false) from "the
  session logic works and the model has a phrasing-specific verbal tic" (true, and a much smaller problem).
- Be able to explain why the fix is a `ContextVar` and not a global mutable variable or thread-local: FastAPI
  request handlers run as concurrent `asyncio` Tasks on one thread, so a thread-local wouldn't isolate anything,
  and a plain global would leak one request's trace into another's under any real concurrency.
- Be honest about the `/internal/*` shared-secret auth if asked: it's not real service-to-service identity, it's
  a placeholder scoped to this DEV demo's actual risk (no PHI, no real users), with the real fix already
  ticketed for Phase 8 rather than hand-waved away.
- Know the actual six tools cold and which backend endpoint each one calls — this is the part of the system most
  likely to come up as "walk me through what happens when a user asks a question."

---

## 2026-09-21 — Phase 6: the public API, the frontend, and the first real browser check

**What:** Built the consumer-facing surface end to end. `backend/src/api/`: `chat.py` (`POST /api/chat`),
`topics.py` (`GET /api/topics` + `GET /api/topics/{id}/knowledge`), `knowledge.py` (`GET /api/knowledge/{id}`,
`GET /api/sources/{id}`), `admin.py` (`GET /api/admin/quality`, `GET /api/admin/agents` + `/{trace_id}`).
`backend/src/services/trace_store.py` (bounded in-memory trace storage). `backend/src/schemas/chat.py`
(Pydantic request/response models). On the frontend: `Assistant.tsx` (real chat UI — question in, grounded
answer + source cards + related-topic chips + disclaimer out), `Topics.tsx` (topic list → click → knowledge
records with status badges), `AdminOverview.tsx` / `AgentObservability.tsx` / `Governance.tsx` (the admin
console, three views over two backend calls), plus a proper `src/types/api.ts` and an expanded `src/api/client.ts`.

**Building the response, not just relaying the agent's text:** `POST /api/chat` doesn't parse the agent's prose
for citations (fragile — depends on the model's exact phrasing, which already varies call to call: "(Source:
know_pcos_004)" one time, "(knowledge_id: know_pcos_004)" the next). Instead, `extract_candidate_knowledge_ids()`
(a pure function, unit tested) pulls the actual `knowledge_id`s out of the agent's trace — specifically, whichever
ones its `search_knowledge` tool call(s) surfaced this turn. That required widening `agents/src/trace.py`'s
`summarize_result()` to keep the IDs, not just a count (see architecture.md's decision log). Backend then
hydrates each ID into a real source card (title, source name, URL, last-reviewed date) via the same
`repositories/bigquery.py` functions the internal API already used, and looks up related topics for whichever
topics those sources belong to. Same repository code, two different callers (the agent's tools, and now the
public API) — no duplication.

**`GET /api/admin/quality` bundles two things the plan treats as related but doesn't fully specify as one
endpoint:** Section 25's data-quality metrics (totals, per-topic eligibility breakdown) and Section 4.2's
"quarantined/non-eligible records" governance view. Both come from the same `semantic.knowledge_catalog` +
`semantic.topic_knowledge_summary` data, and the plan only lists one `/api/admin/quality` route — so
`AdminOverview.tsx` and `Governance.tsx` both call it and render different subsets.

**Trace storage is intentionally not BigQuery.** `trace_store.py` is a bounded (`OrderedDict`, max 200),
process-local, in-memory dict. Building real durable/cross-instance storage now would just be redoing Phase 7's
job (Pub/Sub → Dataflow → BigQuery) early and worse. Documented as a known limitation, not hidden.

**First real browser verification of this project.** Every prior phase was verified with `curl`/`bq query`/pytest
— correct, but never actually looked at as a person would. For Phase 6, used Playwright (no `chromium-cli`
available in this environment, so installed `playwright` + Chromium into an isolated scratch directory rather
than touching the frontend's own `package.json`) to drive the real running app: asked a live question, waited
for the actual answer, and checked the DOM for real source cards and related-topic chips; clicked through
Topics → selected PCOS → saw 6 real knowledge cards including the STALE-badged one; Admin Overview showed
38/33/86.8%/5, matching the numbers computed all the way back in Phase 2's seed data design; Agent Observability
showed the real trace with the actual tool call, args, and candidate IDs; Governance showed exactly the 5
deliberately-seeded non-eligible records. Zero browser console errors. Screenshots taken and inspected at every
step, not just "the command exited 0."

**A debugging detour worth recording:** the very first `POST /api/chat` test after standing up all three
services returned an empty `sources: []` even though the answer text correctly cited two records. Traced it by
reading back the stored trace via `GET /api/admin/agents/{trace_id}` - its `result_summary` only had
`candidate_count`, no `candidate_knowledge_ids`, meaning the running `agents` process was serving an *old*
version of `trace.py` from before this session's widening edit. Root cause: a stale `agents` (and separately, a
stale `backend`) process from Phase 5's testing was still bound to ports 8001/8000, so the new `uvicorn --port
8001` command silently failed to bind (`WinError 10048`) while an old process kept answering health checks
successfully - `/health` returning 200 gave false confidence that "the service is up and current" when only the
first half was true. Found via the actual `WinError` in the redirected log file, not by guessing; fixed by
finding the PID via `netstat -ano` and killing it before restarting. A reminder to check *which* process is
actually listening, not just that *something* is.

**Deviations from the plan:** `GET /api/topics/{topic_id}/knowledge` isn't in the plan's original API list — a
small, explainable, UI-driven addition (Topics.tsx needs it to be an explorer and not just a topic-name list),
not a scope expansion beyond what Section 20 already asks the page to do.

**Interview notes:**
- Be able to explain why citations are extracted from the trace rather than parsed from the model's text — this
  is a "the model is not a reliable source of structured output unless you make it one" point, and the fix
  (widen the trace, don't regex the prose) generalizes well beyond this one feature.
- The stale-process bug is a good "how do you debug something that looks like it's working but isn't" story:
  `/health` returning 200 was misleading precisely because it was *true* (a server was running) while implying
  something false (that server had today's code). The fix was checking the actual bound PID, not trusting the
  green checkmark.
- Know that `/api/admin/quality`'s response is doing double duty for two different frontend pages by design, not
  by accident — a good example of matching an implementation's shape to the API surface the plan actually
  specifies, rather than inventing more endpoints than were asked for.

---
