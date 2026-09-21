# Deliberately minimal: two log-based metrics over Cloud Run's own request logs (which Cloud Run
# emits automatically - no application-level logging changes needed to get these). No alert
# policies or notification channels here - those need a real notification target (email/Slack/etc)
# that shouldn't be created without the person who owns it explicitly asking for it. This gives a
# real, queryable baseline in Cloud Monitoring; alerting is a reasonable next step if this project
# ever needs someone paged, not a DEV-demo requirement.

resource "google_logging_metric" "cloud_run_requests" {
  project = var.project_id
  name    = "shifahealth_cloud_run_requests"
  filter  = "resource.type=\"cloud_run_revision\" AND httpRequest.status>0"

  metric_descriptor {
    metric_kind = "DELTA"
    value_type  = "INT64"
    labels {
      key = "service_name"
    }
    labels {
      key = "status_class"
    }
  }

  label_extractors = {
    "service_name" = "EXTRACT(resource.labels.service_name)"
    "status_class" = "regexp_extract(httpRequest.status, \"([0-9])\\\\d\\\\d\")"
  }
}

resource "google_logging_metric" "cloud_run_server_errors" {
  project = var.project_id
  name    = "shifahealth_cloud_run_5xx_errors"
  filter  = "resource.type=\"cloud_run_revision\" AND httpRequest.status>=500"

  metric_descriptor {
    metric_kind = "DELTA"
    value_type  = "INT64"
    labels {
      key = "service_name"
    }
  }

  label_extractors = {
    "service_name" = "EXTRACT(resource.labels.service_name)"
  }
}
