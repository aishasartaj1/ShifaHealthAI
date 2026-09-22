"""Publish a batch of synthetic interaction events to Pub/Sub, for demo-able analytics/admin
screenshots without waiting on real usage.

    python scripts/generate_demo_events.py --project shifahealthai --sessions 40

This only publishes to the real `shifahealth-events` topic - it does not write to BigQuery
directly. To actually see the numbers move, drain the topic through the real streaming pipeline
and recompute analytics, same as any real traffic would:

    python pipelines/streaming/run.py --project shifahealthai \\
        --subscription shifahealth-events-streaming-sub --run-for-seconds 60
    python scripts/refresh_analytics.py --project shifahealthai

Reuses backend/src/schemas/events.py's build_event() for the wire format (same envelope
production code publishes) rather than hand-rolling event dicts here - anything this script
generates should be indistinguishable, on the wire, from a real interaction.

Every topic_id/knowledge_id referenced is fetched live from BigQuery's currently-eligible
knowledge (semantic.agent_eligible_knowledge), not hardcoded - so this script can't drift out of
sync with whatever the seed data / batch pipeline actually produced.
"""

from __future__ import annotations

import argparse
import json
import random
import sys
import uuid
from datetime import datetime, timedelta, timezone
from pathlib import Path

_BACKEND_SRC = Path(__file__).resolve().parents[1] / "backend"
if str(_BACKEND_SRC) not in sys.path:
    sys.path.insert(0, str(_BACKEND_SRC))

from google.cloud import bigquery, pubsub_v1  # noqa: E402

from src.schemas.events import build_event  # noqa: E402

# Feedback skews positive - a realistic demo corpus of governed, reviewed educational content
# should get more thumbs-up than down.
FEEDBACK_UP_PROBABILITY = 0.8
SOURCE_OPENED_PROBABILITY = 0.7
RELATED_TOPIC_OPENED_PROBABILITY = 0.3
FEEDBACK_SUBMITTED_PROBABILITY = 0.5
RECENT_WINDOW_DAYS = 14


def fetch_eligible_knowledge(client: bigquery.Client, project: str) -> list[dict]:
    query = f"SELECT knowledge_id, topic_id FROM `{project}.semantic.agent_eligible_knowledge`"
    return [dict(row) for row in client.query(query).result()]


def _jittered_timestamp() -> str:
    offset = timedelta(
        days=random.uniform(0, RECENT_WINDOW_DAYS),
        seconds=random.uniform(0, 86400),
    )
    return (datetime.now(timezone.utc) - offset).isoformat()


def build_session_events(catalog: list[dict]) -> list[dict]:
    """One synthetic Q&A session: QUESTION_ASKED -> RESPONSE_GENERATED, then a realistic subset
    of SOURCE_OPENED / RELATED_TOPIC_OPENED / FEEDBACK_SUBMITTED. Returns wire-format event dicts
    with occurred_at spread over a recent window, not all stamped with the same instant."""
    session_id = str(uuid.uuid4())
    trace_id = str(uuid.uuid4())
    primary = random.choice(catalog)
    source_count = random.randint(1, 3)

    events = [
        build_event(event_type="QUESTION_ASKED", session_id=session_id),
        build_event(
            event_type="RESPONSE_GENERATED",
            session_id=session_id,
            trace_id=trace_id,
            latency_ms=round(random.uniform(900, 4500), 1),
            source_count=source_count,
        ),
    ]

    if random.random() < SOURCE_OPENED_PROBABILITY:
        events.append(
            build_event(
                event_type="SOURCE_OPENED",
                session_id=session_id,
                trace_id=trace_id,
                topic_id=primary["topic_id"],
                knowledge_id=primary["knowledge_id"],
            )
        )

    if random.random() < RELATED_TOPIC_OPENED_PROBABILITY:
        related = random.choice(catalog)
        events.append(
            build_event(
                event_type="RELATED_TOPIC_OPENED",
                session_id=session_id,
                trace_id=trace_id,
                topic_id=related["topic_id"],
            )
        )

    if random.random() < FEEDBACK_SUBMITTED_PROBABILITY:
        rating = "up" if random.random() < FEEDBACK_UP_PROBABILITY else "down"
        events.append(
            build_event(event_type="FEEDBACK_SUBMITTED", session_id=session_id, trace_id=trace_id, rating=rating)
        )

    for event in events:
        event["occurred_at"] = _jittered_timestamp()
    return events


def publish_events(publisher: pubsub_v1.PublisherClient, topic_path: str, events: list[dict]) -> None:
    futures = [publisher.publish(topic_path, json.dumps(event).encode("utf-8")) for event in events]
    for future in futures:
        future.result()


def generate(project: str, topic: str, sessions: int) -> int:
    bq_client = bigquery.Client(project=project)
    catalog = fetch_eligible_knowledge(bq_client, project)
    if not catalog:
        print("No agent_eligible_knowledge rows found - nothing to reference. Run the batch pipeline first.")
        return 1

    publisher = pubsub_v1.PublisherClient()
    topic_path = publisher.topic_path(project, topic)

    total_events = 0
    for _ in range(sessions):
        events = build_session_events(catalog)
        publish_events(publisher, topic_path, events)
        total_events += len(events)

    print(f"Published {total_events} events across {sessions} synthetic sessions to {topic_path}")
    print("Next: drain via pipelines/streaming/run.py, then scripts/refresh_analytics.py")
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--project", default="shifahealthai")
    parser.add_argument("--topic", default="shifahealth-events")
    parser.add_argument("--sessions", type=int, default=40)
    args = parser.parse_args()
    return generate(args.project, args.topic, args.sessions)


if __name__ == "__main__":
    sys.exit(main())
