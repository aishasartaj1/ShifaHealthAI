variable "project_id" {
  description = "GCP project ID."
  type        = string
}

variable "location" {
  description = "GCS bucket location (region or multi-region)."
  type        = string
  default     = "us-central1"
}
