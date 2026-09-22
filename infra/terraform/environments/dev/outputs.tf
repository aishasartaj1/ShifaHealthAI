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

output "artifact_registry_repository_url" {
  value = module.artifact_registry.repository_url
}

output "service_accounts" {
  value = {
    backend  = module.iam.backend_service_account_email
    agents   = module.iam.agents_service_account_email
    frontend = module.iam.frontend_service_account_email
  }
}

output "service_urls" {
  value = {
    backend  = module.cloud_run_backend.url
    agents   = module.cloud_run_agents.url
    frontend = module.cloud_run_frontend.url
  }
}

output "cicd" {
  description = "Values GitHub Actions needs (set as repo variables: WORKLOAD_IDENTITY_PROVIDER, CI_SERVICE_ACCOUNT)."
  value = {
    workload_identity_provider = module.cicd.workload_identity_provider
    ci_service_account_email   = module.cicd.ci_service_account_email
  }
}
