output "raw_bucket" {
  value = google_storage_bucket.raw.name
}

output "quarantine_bucket" {
  value = google_storage_bucket.quarantine.name
}
