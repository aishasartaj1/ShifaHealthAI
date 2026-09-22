output "ingestion_signal_topic" {
  value = google_pubsub_topic.ingestion_signals.name
}

output "function_name" {
  value = google_cloudfunctions2_function.raw_file_ingestion_signal.name
}
