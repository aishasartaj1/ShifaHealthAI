"""Request/response shapes for POST /api/chat, matching the plan's Section 14 Response
Presentation: an answer, source cards, related topics, and a fixed educational disclaimer."""

from __future__ import annotations

from pydantic import BaseModel

EDUCATIONAL_DISCLAIMER = "Educational information only; not a substitute for professional medical care."


class ChatRequest(BaseModel):
    message: str
    user_id: str = "anonymous"
    session_id: str | None = None


class SourceCard(BaseModel):
    knowledge_id: str
    title: str
    source_name: str
    source_url: str
    last_reviewed_date: str


class RelatedTopic(BaseModel):
    topic_id: str
    topic_name: str


class ChatResponse(BaseModel):
    answer: str
    sources: list[SourceCard]
    related_topics: list[RelatedTopic]
    disclaimer: str = EDUCATIONAL_DISCLAIMER
    trace_id: str
