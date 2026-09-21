variable "project_id" {
  type = string
}

variable "region" {
  type = string
}

variable "service_name" {
  type = string
}

variable "image" {
  description = "Full Artifact Registry image path, e.g. <repo_url>/backend:tag."
  type        = string
}

variable "service_account_email" {
  type = string
}

variable "allow_unauthenticated" {
  description = "true for backend/frontend (public web traffic); false for agents (only the backend SA's run.invoker binding, granted outside this module, may call it)."
  type        = bool
  default     = false
}

variable "ingress" {
  description = <<-EOT
    INGRESS_TRAFFIC_ALL for every service in this project, including agents (private = IAM-gated,
    not network-gated). INGRESS_TRAFFIC_INTERNAL_ONLY was tried for agents first and found, by
    actually deploying and testing, to require a Serverless VPC Access connector for
    Cloud-Run-to-Cloud-Run calls to work at all - nothing here is configured for that, so it
    silently blocked every caller, including backend itself (see docs/DEVLOG.md's Phase 8 entry).
    IAM (allow_unauthenticated=false + a scoped run.invoker binding) is the real trust boundary,
    consistent with how most production Cloud Run service-to-service auth actually works: identity-
    based (zero-trust), not network-based. Network isolation on top of that is a real option for
    stricter compliance needs, not the default this project's threat model calls for.
  EOT
  type        = string
  default     = "INGRESS_TRAFFIC_ALL"
}

variable "env_vars" {
  description = "Plain (non-secret) environment variables."
  type        = map(string)
  default     = {}
}

variable "secret_env_vars" {
  description = "Environment variables sourced from Secret Manager: { ENV_NAME = { secret_id = \"...\", version = \"latest\" } }"
  type        = map(object({ secret_id = string, version = optional(string, "latest") }))
  default     = {}
}

variable "port" {
  type    = number
  default = 8080
}

variable "cpu" {
  type    = string
  default = "1"
}

variable "memory" {
  type    = string
  default = "512Mi"
}

variable "min_instance_count" {
  description = "0 = scale to zero when idle, avoiding cost between demo sessions."
  type        = number
  default     = 0
}

variable "max_instance_count" {
  description = "Capped low for a DEV portfolio project - bounds both cost and blast radius, not tuned for real traffic."
  type        = number
  default     = 2
}
