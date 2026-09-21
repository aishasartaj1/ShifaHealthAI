# Three datasets matching the plan's layering (Section 9): raw ingestion, curated dimensional
# model, and the semantic/AI-ready layer the agent and API actually read from.
#
# Only the raw tables are defined here, matching what data/seed/*.csv actually loads into today.
# curated.* and semantic.* tables are intentionally deferred to Phase 3, once the Dataflow
# transform logic (dimensional model, ai_eligible computation) that produces them is written —
# defining those schemas now would mean guessing at that logic instead of deriving it.

resource "google_bigquery_dataset" "raw" {
  project     = var.project_id
  dataset_id  = "raw"
  location    = var.location
  description = "Raw ingested data, one-to-one with data/seed/*.csv. Not read directly by the API or agent."
}

resource "google_bigquery_dataset" "curated" {
  project     = var.project_id
  dataset_id  = "curated"
  location    = var.location
  description = "Curated dimensional layer (dim_health_topic, dim_source, dim_knowledge, fact_medical_review, fact_user_question). Populated starting Phase 3."
}

resource "google_bigquery_dataset" "semantic" {
  project     = var.project_id
  dataset_id  = "semantic"
  location    = var.location
  description = "Semantic / AI-ready layer — the governance authority and the only layer the API/agent read from. Populated starting Phase 3."
}

resource "google_bigquery_table" "raw_topics" {
  project             = var.project_id
  dataset_id          = google_bigquery_dataset.raw.dataset_id
  table_id            = "raw_topics"
  deletion_protection = false
  schema              = file("${path.module}/schemas/raw_topics.json")
}

resource "google_bigquery_table" "raw_sources" {
  project             = var.project_id
  dataset_id          = google_bigquery_dataset.raw.dataset_id
  table_id            = "raw_sources"
  deletion_protection = false
  schema              = file("${path.module}/schemas/raw_sources.json")
}

resource "google_bigquery_table" "raw_knowledge" {
  project             = var.project_id
  dataset_id          = google_bigquery_dataset.raw.dataset_id
  table_id            = "raw_knowledge"
  deletion_protection = false
  schema              = file("${path.module}/schemas/raw_knowledge.json")
}

resource "google_bigquery_table" "raw_reviews" {
  project             = var.project_id
  dataset_id          = google_bigquery_dataset.raw.dataset_id
  table_id            = "raw_reviews"
  deletion_protection = false
  schema              = file("${path.module}/schemas/raw_reviews.json")
}
