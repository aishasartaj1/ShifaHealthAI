output "project_id" {
  description = "GCP project ID this DEV environment is provisioned in."
  value       = var.project_id
}

output "region" {
  description = "Default region for regional resources."
  value       = var.region
}

output "enabled_apis" {
  description = "APIs enabled on the project by this configuration."
  value       = local.required_apis
}

output "bigquery_datasets" {
  description = "BigQuery dataset IDs provisioned for the raw/curated/semantic layers."
  value = {
    raw      = module.bigquery.raw_dataset_id
    curated  = module.bigquery.curated_dataset_id
    semantic = module.bigquery.semantic_dataset_id
  }
}

output "storage_buckets" {
  description = "GCS buckets for raw file ingestion (future) and quarantine (Phase 3 batch pipeline)."
  value = {
    raw        = module.storage.raw_bucket
    quarantine = module.storage.quarantine_bucket
  }
}

output "pubsub" {
  description = "Pub/Sub topic and subscription for interaction events (Phase 7)."
  value = {
    topic                  = module.pubsub.topic_name
    streaming_subscription = module.pubsub.streaming_subscription_name
  }
}
