output "backend_service_account_email" {
  value = google_service_account.backend.email
}

output "agents_service_account_email" {
  value = google_service_account.agents.email
}

output "frontend_service_account_email" {
  value = google_service_account.frontend.email
}
