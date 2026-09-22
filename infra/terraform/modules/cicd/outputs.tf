output "workload_identity_provider" {
  description = "Full resource name for the `workload_identity_provider` input of google-github-actions/auth."
  value       = google_iam_workload_identity_pool_provider.github.name
}

output "ci_service_account_email" {
  value = google_service_account.ci.email
}
