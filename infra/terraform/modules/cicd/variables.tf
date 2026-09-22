variable "project_id" {
  type = string
}

variable "github_repository" {
  description = "GitHub repo allowed to federate, as \"owner/name\" (e.g. \"aishasartaj1/ShifaHealthAI\")."
  type        = string
}

variable "app_service_account_emails" {
  description = "Runtime service accounts (backend/agents/frontend) the CI service account needs roles/iam.serviceAccountUser on, to deploy Cloud Run revisions running as them."
  type        = list(string)
}
