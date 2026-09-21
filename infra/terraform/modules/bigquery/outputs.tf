output "raw_dataset_id" {
  value = google_bigquery_dataset.raw.dataset_id
}

output "curated_dataset_id" {
  value = google_bigquery_dataset.curated.dataset_id
}

output "semantic_dataset_id" {
  value = google_bigquery_dataset.semantic.dataset_id
}
