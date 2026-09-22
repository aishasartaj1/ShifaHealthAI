variable "project_id" {
  type = string
}

variable "region" {
  type = string
}

variable "raw_bucket_name" {
  description = "GCS bucket to watch for new-file-arrival events (the `raw` bucket from the storage module)."
  type        = string
}

variable "service_account_email" {
  description = "Service account the function runs as and Eventarc invokes it as."
  type        = string
}
