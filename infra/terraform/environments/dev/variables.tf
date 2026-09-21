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
