output "topic_name" {
  value = google_pubsub_topic.events.name
}

output "streaming_subscription_name" {
  value = google_pubsub_subscription.events_streaming.name
}
