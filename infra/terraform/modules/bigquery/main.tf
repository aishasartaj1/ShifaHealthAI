# Three datasets matching the plan's layering (Section 9): raw ingestion, curated dimensional
# model, and the semantic/AI-ready layer the agent and API actually read from.
#
# curated.* and semantic.* table schemas were added in Phase 3, once pipelines/batch/pipeline.py
# (the Dataflow/Beam job that populates them) existed to derive them from — not guessed ahead of
# that logic in Phase 2. fact_user_question and question_analytics were added in Phase 7 once
# pipelines/streaming/ and scripts/refresh_analytics.py existed to populate them.
#
# Terraform owns schema (CREATE_NEVER in the pipeline's BigQuery writes); the batch pipeline owns
# data (WRITE_TRUNCATE — it recomputes curated/semantic fully on every run).

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
  description = "Curated dimensional layer: dim_health_topic, dim_source, dim_knowledge, fact_medical_review (Phase 3), fact_user_question (Phase 7)."
}

resource "google_bigquery_dataset" "semantic" {
  project     = var.project_id
  dataset_id  = "semantic"
  location    = var.location
  description = "Semantic / AI-ready layer — the governance authority and the only layer the API/agent read from."
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

resource "google_bigquery_table" "dim_health_topic" {
  project             = var.project_id
  dataset_id          = google_bigquery_dataset.curated.dataset_id
  table_id            = "dim_health_topic"
  deletion_protection = false
  schema              = file("${path.module}/schemas/curated_dim_health_topic.json")
}

resource "google_bigquery_table" "dim_source" {
  project             = var.project_id
  dataset_id          = google_bigquery_dataset.curated.dataset_id
  table_id            = "dim_source"
  deletion_protection = false
  schema              = file("${path.module}/schemas/curated_dim_source.json")
}

resource "google_bigquery_table" "dim_knowledge" {
  project             = var.project_id
  dataset_id          = google_bigquery_dataset.curated.dataset_id
  table_id            = "dim_knowledge"
  deletion_protection = false
  schema              = file("${path.module}/schemas/curated_dim_knowledge.json")
}

resource "google_bigquery_table" "fact_medical_review" {
  project             = var.project_id
  dataset_id          = google_bigquery_dataset.curated.dataset_id
  table_id            = "fact_medical_review"
  deletion_protection = false
  schema              = file("${path.module}/schemas/curated_fact_medical_review.json")
}

resource "google_bigquery_table" "knowledge_catalog" {
  project             = var.project_id
  dataset_id          = google_bigquery_dataset.semantic.dataset_id
  table_id            = "knowledge_catalog"
  deletion_protection = false
  schema              = file("${path.module}/schemas/semantic_knowledge_catalog.json")
}

resource "google_bigquery_table" "approved_knowledge" {
  project             = var.project_id
  dataset_id          = google_bigquery_dataset.semantic.dataset_id
  table_id            = "approved_knowledge"
  deletion_protection = false
  schema              = file("${path.module}/schemas/semantic_knowledge_catalog.json") # same shape, filtered to review_status == APPROVED
}

resource "google_bigquery_table" "agent_eligible_knowledge" {
  project             = var.project_id
  dataset_id          = google_bigquery_dataset.semantic.dataset_id
  table_id            = "agent_eligible_knowledge"
  deletion_protection = false
  schema              = file("${path.module}/schemas/semantic_agent_eligible_knowledge.json")
}

resource "google_bigquery_table" "topic_knowledge_summary" {
  project             = var.project_id
  dataset_id          = google_bigquery_dataset.semantic.dataset_id
  table_id            = "topic_knowledge_summary"
  deletion_protection = false
  schema              = file("${path.module}/schemas/semantic_topic_knowledge_summary.json")
}

resource "google_bigquery_table" "knowledge_embeddings" {
  project             = var.project_id
  dataset_id          = google_bigquery_dataset.semantic.dataset_id
  table_id            = "knowledge_embeddings"
  deletion_protection = false
  schema              = file("${path.module}/schemas/semantic_knowledge_embeddings.json")
}

resource "google_bigquery_table" "fact_user_question" {
  project             = var.project_id
  dataset_id          = google_bigquery_dataset.curated.dataset_id
  table_id            = "fact_user_question"
  deletion_protection = false
  schema              = file("${path.module}/schemas/curated_fact_user_question.json")
}

resource "google_bigquery_table" "question_analytics" {
  project             = var.project_id
  dataset_id          = google_bigquery_dataset.semantic.dataset_id
  table_id            = "question_analytics"
  deletion_protection = false
  schema              = file("${path.module}/schemas/semantic_question_analytics.json")
}

resource "google_bigquery_table" "quarantined_events" {
  project             = var.project_id
  dataset_id          = google_bigquery_dataset.curated.dataset_id
  table_id            = "quarantined_events"
  deletion_protection = false
  schema              = file("${path.module}/schemas/curated_quarantined_events.json")
}
