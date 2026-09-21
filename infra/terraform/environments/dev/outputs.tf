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
