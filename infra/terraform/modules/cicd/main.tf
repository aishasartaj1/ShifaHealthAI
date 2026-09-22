# Workload Identity Federation: GitHub Actions authenticates as this project's CI service
# account using a short-lived OIDC token GitHub itself issues per workflow run - no long-lived
# service-account JSON key ever lives in a GitHub secret. This is the current recommended
# pattern for GitHub Actions -> GCP auth (google-github-actions/auth's own docs lead with it).
#
# The CI service account is deliberately NOT granted terraform-apply-level permissions (no
# bigquery.admin, no resourcemanager.projectIamAdmin, etc.) - per the plan's own Section 23
# principle ("Infrastructure changes and application deployments should remain conceptually
# separate"), CI only builds/pushes images and updates existing Cloud Run revisions. Terraform
# apply stays a deliberate manual step, same as every phase so far - see docs/DEVLOG.md's Phase 9
# entry for the reasoning. roles/viewer is granted for `terraform plan`'s read access (so PRs get
# a real plan diff), not for any write capability.

resource "google_iam_workload_identity_pool" "github" {
  project                   = var.project_id
  workload_identity_pool_id = "github-actions-pool"
  display_name              = "GitHub Actions"
}

resource "google_iam_workload_identity_pool_provider" "github" {
  project                            = var.project_id
  workload_identity_pool_id          = google_iam_workload_identity_pool.github.workload_identity_pool_id
  workload_identity_pool_provider_id = "github-actions-provider"
  display_name                       = "GitHub Actions OIDC"

  attribute_mapping = {
    "google.subject"       = "assertion.sub"
    "attribute.repository" = "assertion.repository"
    "attribute.ref"        = "assertion.ref"
  }
  # Only this repo may federate as the CI service account below - any other repo's Actions runs
  # (even under the same GitHub account) are rejected at the token-exchange step.
  attribute_condition = "assertion.repository == \"${var.github_repository}\""

  oidc {
    issuer_uri = "https://token.actions.githubusercontent.com"
  }
}

resource "google_service_account" "ci" {
  project      = var.project_id
  account_id   = "shifahealth-ci"
  display_name = "ShifaHealth CI/CD (GitHub Actions)"
}

resource "google_service_account_iam_member" "github_can_impersonate_ci" {
  service_account_id = google_service_account.ci.name
  role               = "roles/iam.workloadIdentityUser"
  member             = "principalSet://iam.googleapis.com/${google_iam_workload_identity_pool.github.name}/attribute.repository/${var.github_repository}"
}

# Push built images to Artifact Registry.
resource "google_project_iam_member" "ci_artifact_registry_writer" {
  project = var.project_id
  role    = "roles/artifactregistry.writer"
  member  = "serviceAccount:${google_service_account.ci.email}"
}

# Trigger Cloud Build runs (gcloud builds submit) for the image builds.
resource "google_project_iam_member" "ci_cloudbuild_editor" {
  project = var.project_id
  role    = "roles/cloudbuild.builds.editor"
  member  = "serviceAccount:${google_service_account.ci.email}"
}

# Deploy new revisions to the 3 EXISTING Cloud Run services - not create/delete services, and
# never touches ingress/IAM/scaling config, all of which stay Terraform-managed.
resource "google_project_iam_member" "ci_run_developer" {
  project = var.project_id
  role    = "roles/run.developer"
  member  = "serviceAccount:${google_service_account.ci.email}"
}

# Required to deploy a Cloud Run revision that runs as one of the app service accounts, scoped
# to exactly those 3 accounts - not project-wide.
resource "google_service_account_iam_member" "ci_acts_as_app_service_accounts" {
  for_each = toset(var.app_service_account_emails)

  service_account_id = "projects/${var.project_id}/serviceAccounts/${each.value}"
  role               = "roles/iam.serviceAccountUser"
  member             = "serviceAccount:${google_service_account.ci.email}"
}

# Read-only project-wide access so `terraform plan` in the PR workflow can see real state and
# produce a meaningful diff - no write capability comes with this role.
resource "google_project_iam_member" "ci_viewer" {
  project = var.project_id
  role    = "roles/viewer"
  member  = "serviceAccount:${google_service_account.ci.email}"
}

# roles/viewer doesn't cover IAM policy reads or Secret Manager metadata, both of which this
# Terraform config manages - granted narrowly so `plan` can see them without broader write access.
resource "google_project_iam_member" "ci_security_reviewer" {
  project = var.project_id
  role    = "roles/iam.securityReviewer"
  member  = "serviceAccount:${google_service_account.ci.email}"
}

resource "google_project_iam_member" "ci_secretmanager_viewer" {
  project = var.project_id
  role    = "roles/secretmanager.viewer"
  member  = "serviceAccount:${google_service_account.ci.email}"
}
