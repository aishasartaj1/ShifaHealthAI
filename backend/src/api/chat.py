"""POST /api/chat - the public entrypoint for the Women's Health Assistant (plan Section 13's
end-to-end question flow, steps 1-13). Calls the private agents/ service via AgentClient, then
builds source cards + related topics from the agent's trace so the frontend has structured data
to render, not just prose with inline citations. Also publishes QUESTION_ASKED and
RESPONSE_GENERATED interaction events (Section 7.3) - server-side, since this handler is the one
place that actually knows both of those things genuinely happened.
"""

from __future__ import annotations

import time
import uuid

from fastapi import APIRouter

from src.config import get_settings
from src.repositories import bigquery as repo
from src.schemas.chat import ChatRequest, ChatResponse, RelatedTopic, SourceCard
from src.schemas.events import build_event
from src.services.agent_client import AgentClient
from src.services.pubsub import publish_event
from src.services.trace_store import record_trace

router = APIRouter(prefix="/api", tags=["chat"])

MAX_SOURCES = 3
RELATED_TOPICS_PER_SOURCE = 2


def extract_candidate_knowledge_ids(trace: dict) -> list[str]:
    """Pure: pulls the knowledge_ids the agent's search_knowledge tool call(s) surfaced this
    turn, in order, deduped. trace is the {"tool_calls": [...]} shape agents/src/trace.py
    produces - see its summarize_result() for why knowledge_ids (not just counts) are in there."""
    ids: list[str] = []
    for call in trace.get("tool_calls", []):
        if call.get("tool") != "search_knowledge":
            continue
        for knowledge_id in call.get("result_summary", {}).get("candidate_knowledge_ids", []):
            if knowledge_id and knowledge_id not in ids:
                ids.append(knowledge_id)
    return ids


@router.post("/chat", response_model=ChatResponse)
def chat(body: ChatRequest) -> ChatResponse:
    settings = get_settings()
    bq_client = repo.get_bigquery_client()
    session_id = body.session_id or body.user_id

    publish_event(build_event(event_type="QUESTION_ASKED", session_id=session_id))

    started_at = time.monotonic()
    agent_result = AgentClient().invoke(body.message, user_id=body.user_id, session_id=session_id)
    agent_trace = agent_result.get("trace", {})
    candidate_ids = extract_candidate_knowledge_ids(agent_trace)[:MAX_SOURCES]

    sources: list[SourceCard] = []
    related_topics: list[RelatedTopic] = []
    seen_topic_ids: set[str] = set()

    for knowledge_id in candidate_ids:
        record = repo.get_knowledge_record(bq_client, settings.gcp_project_id, knowledge_id)
        if record is None:
            continue
        source = repo.get_source_record(bq_client, settings.gcp_project_id, record["source_id"])
        sources.append(
            SourceCard(
                knowledge_id=record["knowledge_id"],
                title=record["title"],
                source_name=record.get("source_name", ""),
                source_url=source["url"] if source else "",
                last_reviewed_date=str(record["last_reviewed_date"]),
            )
        )

        if record["topic_id"] in seen_topic_ids:
            continue
        seen_topic_ids.add(record["topic_id"])
        for related in repo.list_related_topics(
            bq_client, settings.gcp_project_id, record["topic_id"], limit=RELATED_TOPICS_PER_SOURCE
        ):
            if related["topic_id"] in seen_topic_ids:
                continue
            seen_topic_ids.add(related["topic_id"])
            related_topics.append(RelatedTopic(topic_id=related["topic_id"], topic_name=related["topic_name"]))

    total_latency_ms = round((time.monotonic() - started_at) * 1000, 1)

    trace_id = str(uuid.uuid4())
    record_trace(
        trace_id,
        {
            "trace_id": trace_id,
            "question": body.message,
            "tool_calls": agent_trace.get("tool_calls", []),
            "total_latency_ms": agent_trace.get("total_latency_ms"),
            "candidate_knowledge_ids": candidate_ids,
        },
    )

    publish_event(
        build_event(
            event_type="RESPONSE_GENERATED",
            session_id=session_id,
            trace_id=trace_id,
            latency_ms=total_latency_ms,
            source_count=len(sources),
        )
    )

    return ChatResponse(
        answer=agent_result["response"],
        sources=sources,
        related_topics=related_topics,
        trace_id=trace_id,
    )
