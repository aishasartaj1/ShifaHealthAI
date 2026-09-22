# One service account per Cloud Run service, each with only the project-level roles that
# service actually calls. The one binding that matters most (backend's SA -> roles/run.invoker
# scoped to the agents service specifically, not project-wide) lives in the dev environment root,
# not here - it needs the agents Cloud Run service to already exist, which this module doesn't
# create (see architecture.md's Service Topology / "The two HTTP relationships").

resource "google_service_account" "backend" {
  project      = var.project_id
  account_id   = "shifahealth-backend"
  display_name = "ShifaHealth backend (FastAPI, public ingress)"
}

resource "google_service_account" "agents" {
  project      = var.project_id
  account_id   = "shifahealth-agents"
  display_name = "ShifaHealth agents (ADK, private ingress)"
}

resource "google_service_account" "frontend" {
  project      = var.project_id
  account_id   = "shifahealth-frontend"
  display_name = "ShifaHealth frontend (static SPA, public ingress)"
}

resource "google_service_account" "functions" {
  project      = var.project_id
  account_id   = "shifahealth-functions"
  display_name = "ShifaHealth ingestion-signal Cloud Function"
}

# backend: reads BigQuery (retrieval + admin APIs), runs embedding calls, publishes interaction
# events. No write access to BigQuery - all writes happen through the batch/streaming pipelines,
# run separately under the operator's own credentials, never through the running service.
resource "google_project_iam_member" "backend_bigquery_data_viewer" {
  project = var.project_id
  role    = "roles/bigquery.dataViewer"
  member  = "serviceAccount:${google_service_account.backend.email}"
}

resource "google_project_iam_member" "backend_bigquery_job_user" {
  project = var.project_id
  role    = "roles/bigquery.jobUser"
  member  = "serviceAccount:${google_service_account.backend.email}"
}

resource "google_project_iam_member" "backend_aiplatform_user" {
  project = var.project_id
  role    = "roles/aiplatform.user"
  member  = "serviceAccount:${google_service_account.backend.email}"
}

resource "google_project_iam_member" "backend_pubsub_publisher" {
  project = var.project_id
  role    = "roles/pubsub.publisher"
  member  = "serviceAccount:${google_service_account.backend.email}"
}

# agents: only needs to call Gemini. It has no BigQuery/Pub/Sub access of its own by design -
# every retrieval/lookup it needs goes through backend's /internal/* API instead.
resource "google_project_iam_member" "agents_aiplatform_user" {
  project = var.project_id
  role    = "roles/aiplatform.user"
  member  = "serviceAccount:${google_service_account.agents.email}"
}

# frontend: intentionally no extra roles. It's a static file server; least privilege here means
# literally nothing beyond what Cloud Run grants by default.
