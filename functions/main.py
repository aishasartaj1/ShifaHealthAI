"""Cloud Function entrypoint: on a new object landing in the `raw` bucket, publish a small
structured ingestion signal to Pub/Sub. Deliberately does nothing else - see the plan's Section 17
and docs/architecture.md's GCP services table for why this stays one small event-triggered
responsibility rather than a second ingestion path alongside pipelines/batch."""

from __future__ import annotations

import json
import logging
import os
from functools import lru_cache

import functions_framework
from cloudevents.http import CloudEvent
from google.cloud import pubsub_v1

from transform import build_ingestion_signal

logger = logging.getLogger(__name__)


@lru_cache
def _get_publisher_client() -> pubsub_v1.PublisherClient:
    return pubsub_v1.PublisherClient()


@functions_framework.cloud_event
def on_raw_file_arrival(cloud_event: CloudEvent) -> None:
    signal = build_ingestion_signal(cloud_event.data)

    client = _get_publisher_client()
    topic_path = client.topic_path(
        os.environ["GCP_PROJECT_ID"], os.environ["INGESTION_SIGNAL_TOPIC"]
    )
    client.publish(topic_path, json.dumps(signal).encode("utf-8")).result()

    logger.info(
        "Published ingestion signal for gs://%s/%s", signal["bucket"], signal["object_name"]
    )
