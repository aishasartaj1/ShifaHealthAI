# One topic for the 5 interaction event types (Section 7.3): QUESTION_ASKED, RESPONSE_GENERATED
# (published server-side by backend/src/api/chat.py), SOURCE_OPENED, RELATED_TOPIC_OPENED,
# FEEDBACK_SUBMITTED (published by backend/src/api/events.py on the frontend's behalf).
#
# One pull subscription for pipelines/streaming/pipeline.py to read from. No dead-letter topic -
# the streaming pipeline's own validate-and-quarantine step (same GCS quarantine bucket the batch
# pipeline uses) is the invalid-message handling, not a second Pub/Sub-level mechanism.

resource "google_pubsub_topic" "events" {
  project = var.project_id
  name    = "shifahealth-events"
}

resource "google_pubsub_subscription" "events_streaming" {
  project = var.project_id
  name    = "shifahealth-events-streaming-sub"
  topic   = google_pubsub_topic.events.name

  ack_deadline_seconds       = 30
  message_retention_duration = "86400s" # 1 day - plenty for a DEV demo, not tuned for real volume
}
