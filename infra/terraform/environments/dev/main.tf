terraform {
  required_version = ">= 1.9"

  required_providers {
    google = {
      source  = "hashicorp/google"
      version = "~> 6.0"
    }
    random = {
      source  = "hashicorp/random"
      version = "~> 3.6"
    }
    archive = {
      source  = "hashicorp/archive"
      version = "~> 2.4"
    }
  }
}

provider "google" {
  project = var.project_id
  region  = var.region
}

# APIs required across the phases in docs/BACKLOG.md. Enabled here, once, at the project level —
# individual modules (bigquery, cloud_run, pubsub, ...) added in later phases depend on these
# already being on rather than each re-declaring the APIs they need.
locals {
  required_apis = [
    "run.googleapis.com",              # Cloud Run (FastAPI backend serving)
    "artifactregistry.googleapis.com", # container images
    "bigquery.googleapis.com",         # raw/curated/semantic layers, governance, analytics
    "bigquerystorage.googleapis.com",  # BigQuery Storage Read API - used by Beam's DIRECT_READ
    "storage.googleapis.com",          # Cloud Storage raw + quarantine buckets
    "pubsub.googleapis.com",           # streaming application events
    "dataflow.googleapis.com",         # batch + streaming pipelines
    "aiplatform.googleapis.com",       # Vertex AI Gemini + embeddings
    "cloudfunctions.googleapis.com",   # event-driven ingestion trigger
    "cloudbuild.googleapis.com",       # container builds for Cloud Run / Functions
    "secretmanager.googleapis.com",    # runtime secrets
    "iam.googleapis.com",              # service account management
    "logging.googleapis.com",          # observability
    "monitoring.googleapis.com",       # observability
    "eventarc.googleapis.com",         # GCS-triggered Cloud Function (2nd gen)
    "iamcredentials.googleapis.com",   # Workload Identity Federation token exchange (GitHub Actions CI/CD)
    "sts.googleapis.com",              # Workload Identity Federation token exchange
  ]
}

resource "google_project_service" "required" {
  for_each = toset(local.required_apis)

  project            = var.project_id
  service            = each.value
  disable_on_destroy = false
}

module "bigquery" {
  source     = "../../modules/bigquery"
  project_id = var.project_id
  location   = var.region

  depends_on = [google_project_service.required]
}

module "storage" {
  source     = "../../modules/storage"
  project_id = var.project_id
  location   = var.region

  depends_on = [google_project_service.required]
}

module "pubsub" {
  source     = "../../modules/pubsub"
  project_id = var.project_id

  depends_on = [google_project_service.required]
}

module "artifact_registry" {
  source     = "../../modules/artifact_registry"
  project_id = var.project_id
  region     = var.region

  depends_on = [google_project_service.required]
}

module "iam" {
  source     = "../../modules/iam"
  project_id = var.project_id

  depends_on = [google_project_service.required]
}

module "observability" {
  source     = "../../modules/observability"
  project_id = var.project_id

  depends_on = [google_project_service.required]
}

# Shared secret for backend/src/api/internal.py's fallback auth path (used only when no Google ID
# token is presented - see that file's module docstring and docs/DEVLOG.md's Phase 8 entry for the
# real ID-token verification this secret is a fallback alongside, not a replacement for).
resource "random_password" "internal_api_key" {
  length  = 32
  special = false
}

resource "google_secret_manager_secret" "internal_api_key" {
  project   = var.project_id
  secret_id = "shifahealth-internal-api-key"

  replication {
    auto {}
  }

  depends_on = [google_project_service.required]
}

resource "google_secret_manager_secret_version" "internal_api_key" {
  secret      = google_secret_manager_secret.internal_api_key.id
  secret_data = random_password.internal_api_key.result
}

resource "google_secret_manager_secret_iam_member" "backend_reads_internal_api_key" {
  project   = var.project_id
  secret_id = google_secret_manager_secret.internal_api_key.secret_id
  role      = "roles/secretmanager.secretAccessor"
  member    = "serviceAccount:${module.iam.backend_service_account_email}"
}

resource "google_secret_manager_secret_iam_member" "agents_reads_internal_api_key" {
  project   = var.project_id
  secret_id = google_secret_manager_secret.internal_api_key.secret_id
  role      = "roles/secretmanager.secretAccessor"
  member    = "serviceAccount:${module.iam.agents_service_account_email}"
}

locals {
  # backend and agents each need the OTHER's real URL in their env vars (to call each other, and
  # for backend to verify an incoming ID token's audience against its own URL). Referencing
  # module.cloud_run_backend.url from agents' config AND module.cloud_run_agents.url from
  # backend's config would be a genuine circular Terraform dependency - neither could be planned
  # first. var.cloud_run_url_suffix (see variables.tf) breaks the cycle: both URLs are derived
  # from a plain variable, not from each other's resource output, so there's no cycle - just two
  # independent computations that happen to agree, confirmed against the real .uri outputs.
  backend_url  = "https://backend-${var.cloud_run_url_suffix}.a.run.app"
  agents_url   = "https://agents-${var.cloud_run_url_suffix}.a.run.app"
  frontend_url = "https://frontend-${var.cloud_run_url_suffix}.a.run.app"
}

module "cloud_run_backend" {
  source                = "../../modules/cloud_run"
  project_id            = var.project_id
  region                = var.region
  service_name          = "backend"
  image                 = "${module.artifact_registry.repository_url}/backend:latest"
  service_account_email = module.iam.backend_service_account_email
  allow_unauthenticated = true
  ingress               = "INGRESS_TRAFFIC_ALL"

  env_vars = {
    ENVIRONMENT                  = "cloud"
    GCP_PROJECT_ID               = var.project_id
    GCP_REGION                   = var.region
    CORS_ALLOW_ORIGINS           = jsonencode([local.frontend_url])
    AGENT_SERVICE_BASE_URL       = local.agents_url
    PUBLIC_BASE_URL              = local.backend_url
    AGENTS_SERVICE_ACCOUNT_EMAIL = module.iam.agents_service_account_email
    PUBSUB_TOPIC                 = module.pubsub.topic_name
  }

  secret_env_vars = {
    INTERNAL_API_KEY = { secret_id = google_secret_manager_secret.internal_api_key.secret_id }
  }

  depends_on = [google_project_service.required, google_secret_manager_secret_version.internal_api_key]
}

module "cloud_run_agents" {
  source                = "../../modules/cloud_run"
  project_id            = var.project_id
  region                = var.region
  service_name          = "agents"
  image                 = "${module.artifact_registry.repository_url}/agents:latest"
  service_account_email = module.iam.agents_service_account_email
  allow_unauthenticated = false
  # ingress: default (INGRESS_TRAFFIC_ALL) - see the cloud_run module's variable description for
  # why INTERNAL_ONLY doesn't work here without a VPC connector this project doesn't have.

  env_vars = {
    ENVIRONMENT      = "cloud"
    GCP_PROJECT_ID   = var.project_id
    GCP_REGION       = var.region
    GEMINI_MODEL     = "gemini-2.5-flash"
    BACKEND_BASE_URL = local.backend_url
  }

  secret_env_vars = {
    INTERNAL_API_KEY = { secret_id = google_secret_manager_secret.internal_api_key.secret_id }
  }

  depends_on = [google_project_service.required, google_secret_manager_secret_version.internal_api_key]
}

# The enforced trust boundary from architecture.md's Service Topology: only backend's service
# account may invoke agents (IAM-gated, not network-gated - see the cloud_run module's `ingress`
# variable description for why), and only on this one service - not project-wide.
resource "google_cloud_run_v2_service_iam_member" "backend_invokes_agents" {
  project  = var.project_id
  location = var.region
  name     = module.cloud_run_agents.service_name
  role     = "roles/run.invoker"
  member   = "serviceAccount:${module.iam.backend_service_account_email}"
}

module "cloud_run_frontend" {
  source                = "../../modules/cloud_run"
  project_id            = var.project_id
  region                = var.region
  service_name          = "frontend"
  image                 = "${module.artifact_registry.repository_url}/frontend:latest"
  service_account_email = module.iam.frontend_service_account_email
  allow_unauthenticated = true

  # No env_vars: VITE_API_BASE_URL is baked into the built JS bundle at image-build time (a Vite
  # build-arg, see frontend/Dockerfile), not read from the environment at runtime - nginx serves
  # static files and has no notion of these values.

  depends_on = [google_project_service.required]
}

module "functions" {
  source                = "../../modules/functions"
  project_id            = var.project_id
  region                = var.region
  raw_bucket_name       = module.storage.raw_bucket
  service_account_email = module.iam.functions_service_account_email

  depends_on = [google_project_service.required]
}

module "cicd" {
  source            = "../../modules/cicd"
  project_id        = var.project_id
  github_repository = "aishasartaj1/ShifaHealthAI"
  app_service_account_emails = [
    module.iam.backend_service_account_email,
    module.iam.agents_service_account_email,
    module.iam.frontend_service_account_email,
  ]

  depends_on = [google_project_service.required]
}
