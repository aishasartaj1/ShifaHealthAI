terraform {
  required_version = ">= 1.9"

  required_providers {
    google = {
      source  = "hashicorp/google"
      version = "~> 6.0"
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
    "run.googleapis.com",               # Cloud Run (FastAPI backend serving)
    "artifactregistry.googleapis.com",  # container images
    "bigquery.googleapis.com",          # raw/curated/semantic layers, governance, analytics
    "bigquerystorage.googleapis.com",   # BigQuery Storage Read API - used by Beam's DIRECT_READ
    "storage.googleapis.com",           # Cloud Storage raw + quarantine buckets
    "pubsub.googleapis.com",            # streaming application events
    "dataflow.googleapis.com",          # batch + streaming pipelines
    "aiplatform.googleapis.com",        # Vertex AI Gemini + embeddings
    "cloudfunctions.googleapis.com",    # event-driven ingestion trigger
    "cloudbuild.googleapis.com",        # container builds for Cloud Run / Functions
    "secretmanager.googleapis.com",     # runtime secrets
    "iam.googleapis.com",               # service account management
    "logging.googleapis.com",           # observability
    "monitoring.googleapis.com",        # observability
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
