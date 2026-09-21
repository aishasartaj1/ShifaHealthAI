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
