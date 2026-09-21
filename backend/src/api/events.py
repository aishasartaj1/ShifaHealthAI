"""POST /api/events - the interaction-event sink for the three genuinely client-side events
(SOURCE_OPENED, RELATED_TOPIC_OPENED, FEEDBACK_SUBMITTED). QUESTION_ASKED and RESPONSE_GENERATED
are published directly by chat.py, which is why EventRequest's event_type doesn't include them.
"""

from __future__ import annotations

from fastapi import APIRouter

from src.schemas.events import EventRequest, build_event
from src.services.pubsub import publish_event

router = APIRouter(prefix="/api", tags=["events"])


@router.post("/events", status_code=202)
def post_event(body: EventRequest) -> dict:
    event = build_event(
        event_type=body.event_type,
        session_id=body.session_id,
        trace_id=body.trace_id,
        topic_id=body.topic_id,
        knowledge_id=body.knowledge_id,
        rating=body.rating,
    )
    publish_event(event)
    return {"status": "accepted", "event_id": event["event_id"]}
