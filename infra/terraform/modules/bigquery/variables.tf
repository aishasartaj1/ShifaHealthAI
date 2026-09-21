variable "project_id" {
  description = "GCP project ID."
  type        = string
}

variable "location" {
  description = "BigQuery dataset location (region or multi-region, e.g. 'us-central1' or 'US')."
  type        = string
  default     = "us-central1"
}
