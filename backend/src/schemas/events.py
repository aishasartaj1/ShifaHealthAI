"""The 5 interaction event types from the plan's Section 7.3, published to Pub/Sub and eventually
landing in curated.fact_user_question via pipelines/streaming/.

Deliberately no free-text field anywhere in this schema - not the question text, not the answer
text. Section 16 of the plan is explicit: "avoid collecting sensitive or identifying health
information... anonymous operational telemetry." Structural metadata (which event, which topic,
which knowledge_id, latency, a thumbs up/down) is enough for analytics without ever writing a
user's actual health question into a table.
"""

from __future__ import annotations

import uuid
from datetime import UTC, datetime
from typing import Literal

from pydantic import BaseModel

EventType = Literal[
    "QUESTION_ASKED",
    "RESPONSE_GENERATED",
    "SOURCE_OPENED",
    "RELATED_TOPIC_OPENED",
    "FEEDBACK_SUBMITTED",
]

# QUESTION_ASKED and RESPONSE_GENERATED are published server-side by api/chat.py, which knows
# they genuinely happened. Accepting them from POST /api/events would let a client fabricate
# analytics events that never corresponded to a real backend/agent call.
CLIENT_FIREABLE_EVENT_TYPES: set[str] = {"SOURCE_OPENED", "RELATED_TOPIC_OPENED", "FEEDBACK_SUBMITTED"}


class EventRequest(BaseModel):
    event_type: Literal["SOURCE_OPENED", "RELATED_TOPIC_OPENED", "FEEDBACK_SUBMITTED"]
    session_id: str
    trace_id: str | None = None
    topic_id: str | None = None
    knowledge_id: str | None = None
    rating: Literal["up", "down"] | None = None


def build_event(
    event_type: EventType,
    session_id: str,
    trace_id: str | None = None,
    topic_id: str | None = None,
    knowledge_id: str | None = None,
    rating: str | None = None,
    latency_ms: float | None = None,
    source_count: int | None = None,
) -> dict:
    """Pure: builds the wire-format event dict. event_id/occurred_at are generated here so
    every publisher (chat.py, events.py) produces a consistent envelope."""
    return {
        "event_id": str(uuid.uuid4()),
        "event_type": event_type,
        "session_id": session_id,
        "trace_id": trace_id,
        "topic_id": topic_id,
        "knowledge_id": knowledge_id,
        "rating": rating,
        "latency_ms": latency_ms,
        "source_count": source_count,
        "occurred_at": datetime.now(UTC).isoformat(),
    }
