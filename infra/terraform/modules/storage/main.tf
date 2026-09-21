# "raw" holds source documents/files for future real ingestion (Phase 8's Cloud Function watches
# it for new-file events). It is NOT currently how the seed data gets into BigQuery — that went
# straight from data/seed/*.csv via scripts/seed_bigquery.py (Phase 2) — but it's provisioned now
# since the plan's ingestion diagram routes through it and Phase 8 needs it to exist.
#
# "quarantine" is where pipelines/batch/pipeline.py (Phase 3) writes rows that failed validation,
# as newline-delimited JSON, one prefix per raw table per run.

resource "google_storage_bucket" "raw" {
  project                     = var.project_id
  name                        = "${var.project_id}-raw"
  location                    = var.location
  uniform_bucket_level_access = true
  force_destroy               = true # DEV-only convenience; would not be set in a real environment.
}

resource "google_storage_bucket" "quarantine" {
  project                     = var.project_id
  name                        = "${var.project_id}-quarantine"
  location                    = var.location
  uniform_bucket_level_access = true
  force_destroy               = true
}
