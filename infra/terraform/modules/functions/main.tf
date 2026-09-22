# One small Cloud Function (Section 17 of the plan): a new object landing in the `raw` bucket
# triggers this function via Eventarc, and it does nothing but publish a small structured signal
# to its own Pub/Sub topic. No downstream consumer is built - the point is demonstrating the
# event-driven wiring itself, not moving real ingestion logic out of pipelines/batch.

resource "google_pubsub_topic" "ingestion_signals" {
  project = var.project_id
  name    = "shifahealth-ingestion-signals"
}

data "archive_file" "source" {
  type        = "zip"
  source_dir  = "${path.module}/../../../../functions"
  output_path = "${path.module}/.build/function-source.zip"
  excludes = [
    "tests", "__pycache__", ".venv", ".pytest_cache", ".ruff_cache",
    "requirements-dev.txt", "pyproject.toml",
  ]
}

# Dedicated bucket for the function's own source zip - not the `raw` bucket this function is
# triggered by, since uploading source there would trigger the function on its own deploys.
resource "google_storage_bucket" "function_source" {
  project                     = var.project_id
  name                        = "${var.project_id}-functions-source"
  location                    = var.region
  uniform_bucket_level_access = true
  force_destroy               = true
}

resource "google_storage_bucket_object" "source_zip" {
  name   = "raw-file-ingestion-signal/source-${data.archive_file.source.output_md5}.zip"
  bucket = google_storage_bucket.function_source.name
  source = data.archive_file.source.output_path
}

# Scoped to this one topic, not project-wide Pub/Sub access.
resource "google_pubsub_topic_iam_member" "function_publishes_ingestion_signals" {
  project = var.project_id
  topic   = google_pubsub_topic.ingestion_signals.name
  role    = "roles/pubsub.publisher"
  member  = "serviceAccount:${var.service_account_email}"
}

# GCS's own service agent needs to publish to Eventarc's underlying transport for the
# `google.cloud.storage.object.v1.finalized` trigger to ever fire - a one-time, Google-managed
# grant, distinct from any role this function's own service account holds.
data "google_storage_project_service_account" "gcs" {
  project = var.project_id
}

resource "google_project_iam_member" "gcs_publishes_to_eventarc" {
  project = var.project_id
  role    = "roles/pubsub.publisher"
  member  = "serviceAccount:${data.google_storage_project_service_account.gcs.email_address}"
}

resource "google_project_iam_member" "functions_eventarc_event_receiver" {
  project = var.project_id
  role    = "roles/eventarc.eventReceiver"
  member  = "serviceAccount:${var.service_account_email}"
}

# Eventarc validates the trigger's source bucket at creation time by calling storage.buckets.get
# AS the trigger's own service account - separate from the GCS-service-agent grant above (which
# only covers publishing the actual finalize notifications). Scoped to just the `raw` bucket, not
# project-wide storage access. Found by the first real `terraform apply` of this module.
resource "google_storage_bucket_iam_member" "functions_reads_raw_bucket_metadata" {
  bucket = var.raw_bucket_name
  role   = "roles/storage.objectViewer"
  member = "serviceAccount:${var.service_account_email}"
}

resource "google_cloudfunctions2_function" "raw_file_ingestion_signal" {
  project  = var.project_id
  name     = "raw-file-ingestion-signal"
  location = var.region

  build_config {
    runtime     = "python312"
    entry_point = "on_raw_file_arrival"
    source {
      storage_source {
        bucket = google_storage_bucket.function_source.name
        object = google_storage_bucket_object.source_zip.name
      }
    }
  }

  service_config {
    max_instance_count    = 1
    available_memory      = "256M"
    timeout_seconds       = 60
    service_account_email = var.service_account_email
    ingress_settings      = "ALLOW_INTERNAL_ONLY"

    environment_variables = {
      GCP_PROJECT_ID         = var.project_id
      INGESTION_SIGNAL_TOPIC = google_pubsub_topic.ingestion_signals.name
    }
  }

  event_trigger {
    trigger_region        = var.region
    event_type            = "google.cloud.storage.object.v1.finalized"
    retry_policy          = "RETRY_POLICY_DO_NOT_RETRY"
    service_account_email = var.service_account_email

    event_filters {
      attribute = "bucket"
      value     = var.raw_bucket_name
    }
  }

  depends_on = [
    google_project_iam_member.gcs_publishes_to_eventarc,
    google_project_iam_member.functions_eventarc_event_receiver,
    google_pubsub_topic_iam_member.function_publishes_ingestion_signals,
    google_storage_bucket_iam_member.functions_reads_raw_bucket_metadata,
  ]
}

# Eventarc invokes the function's underlying Cloud Run service directly - needs run.invoker on
# that specific service, not just eventarc.eventReceiver at the project level.
resource "google_cloud_run_service_iam_member" "eventarc_invokes_function" {
  project  = var.project_id
  location = var.region
  service  = google_cloudfunctions2_function.raw_file_ingestion_signal.name
  role     = "roles/run.invoker"
  member   = "serviceAccount:${var.service_account_email}"
}
