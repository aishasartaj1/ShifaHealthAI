variable "project_id" {
  description = "GCP project ID for the DEV environment."
  type        = string
}

variable "region" {
  description = "Default GCP region for regional resources."
  type        = string
  default     = "us-central1"
}

variable "environment" {
  description = "Deployment environment label. This project provisions 'dev' only."
  type        = string
  default     = "dev"
}

variable "cloud_run_url_suffix" {
  description = <<-EOT
    The opaque per-project+region suffix Cloud Run uses in its default .a.run.app URLs, e.g.
    "u7f3tlft2q-uc" in https://backend-u7f3tlft2q-uc.a.run.app. NOT derivable in advance from
    project number/region via any documented formula (a first guess at that was wrong - see
    docs/DEVLOG.md's Phase 8 entry) - discovered empirically by creating any one Cloud Run
    service in this project+region and reading its real `.uri` output, then hardcoded here so
    backend/agents/frontend can reference each other's URLs in env vars without forming a
    circular Terraform dependency (each needing the others' *actual* .uri output would be a
    genuine cycle). Stable per project+region once known; redetermine if either ever changes.
  EOT
  type        = string
}
