# One Docker repository holds all three service images (backend, agents, frontend) - a single
# small DEV project doesn't need per-service repos, and it keeps the module list matching the
# plan's Section 21 GCP services table ("Artifact Registry | Container images").

resource "google_artifact_registry_repository" "images" {
  project       = var.project_id
  location      = var.region
  repository_id = "shifahealth"
  format        = "DOCKER"
  description   = "Container images for backend, agents, and frontend."
}
