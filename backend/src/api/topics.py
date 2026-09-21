from __future__ import annotations

from fastapi import APIRouter

from src.config import get_settings
from src.repositories import bigquery as repo

router = APIRouter(prefix="/api", tags=["topics"])


@router.get("/topics")
def list_topics() -> list[dict]:
    settings = get_settings()
    return repo.list_topics(repo.get_bigquery_client(), settings.gcp_project_id)


@router.get("/topics/{topic_id}/knowledge")
def list_topic_knowledge(topic_id: str) -> list[dict]:
    """Not in the plan's original Section 19 API list - added so the topic explorer
    (frontend Topics.tsx) has something to show once a topic is selected. See docs/DEVLOG.md."""
    settings = get_settings()
    return repo.list_knowledge_by_topic(repo.get_bigquery_client(), settings.gcp_project_id, topic_id)
