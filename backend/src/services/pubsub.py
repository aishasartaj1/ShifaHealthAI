"""Publishes interaction events to Pub/Sub. Best-effort: a publish failure never breaks the
user-facing request it's attached to - telemetry is not allowed to take down the chat flow."""

from __future__ import annotations

import json
import logging
from functools import lru_cache

from google.cloud import pubsub_v1

from src.config import get_settings

logger = logging.getLogger(__name__)


@lru_cache
def get_publisher_client() -> pubsub_v1.PublisherClient:
    return pubsub_v1.PublisherClient()


def publish_event(event: dict) -> None:
    settings = get_settings()
    client = get_publisher_client()
    topic_path = client.topic_path(settings.gcp_project_id, settings.pubsub_topic)
    future = client.publish(topic_path, json.dumps(event).encode("utf-8"))
    future.add_done_callback(_log_publish_result)


def _log_publish_result(future) -> None:
    try:
        future.result()
    except Exception:  # noqa: BLE001 - best-effort telemetry, never raises into the caller
        logger.warning("Failed to publish event to Pub/Sub", exc_info=True)
