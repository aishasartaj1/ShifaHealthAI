output "repository_url" {
  description = "Base URL for pushing/pulling images, e.g. <url>/backend:tag"
  value       = "${var.region}-docker.pkg.dev/${var.project_id}/${google_artifact_registry_repository.images.repository_id}"
}
