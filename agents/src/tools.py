"""The six agent tools from the plan's Section 12. Each is a thin HTTP call into backend's
/internal/* API (src/api/internal.py) — this service holds no BigQuery/Vertex AI credentials of
its own and never touches retrieval data directly; that's backend's job (see architecture.md's
Service Topology). Plain functions with type hints + docstrings, since ADK auto-generates each
tool's function-calling schema from exactly those two things.
"""

from __future__ import annotations

import logging

import httpx
from google.auth.transport import requests as google_auth_requests
from google.oauth2 import id_token as google_id_token

from src.config import get_settings

logger = logging.getLogger(__name__)


def _auth_headers(settings) -> dict[str, str]:
    """Real service identity when it's available (a Google-signed ID token, minted for exactly
    backend's URL as audience - see backend/src/api/internal.py's _verify_id_token), with the
    shared-secret header always attached too as the local-dev fallback backend uses when no
    Bearer token is present. fetch_id_token requires ambient SERVICE ACCOUNT credentials (true on
    a real Cloud Run instance); a human's ADC credentials (local dev) can't mint one and this
    raises - caught here, not treated as fatal, since the shared secret still gets the call through
    locally. Skipped entirely when environment=="dev": discovering that ADC can't mint a token
    takes several real seconds per call (multiple credential sources tried before giving up), a
    cost worth avoiding rather than paying and catching on every local request."""
    headers = {"X-Internal-Api-Key": settings.internal_api_key}
    if settings.environment == "dev":
        return headers
    try:
        token = google_id_token.fetch_id_token(google_auth_requests.Request(), settings.backend_base_url)
        headers["Authorization"] = f"Bearer {token}"
    except Exception:
        logger.debug("No ID token available (expected in local dev); falling back to shared secret.")
    return headers


def _client() -> httpx.Client:
    settings = get_settings()
    return httpx.Client(base_url=settings.backend_base_url, headers=_auth_headers(settings), timeout=30.0)


def search_knowledge(query: str, topic: str = "") -> dict:
    """Search the governed women's-health knowledge base using hybrid semantic + lexical retrieval.

    Use this for any educational question about women's health. Only returns content that is
    CURRENTLY governance-eligible (approved, from an active source, not stale) - never invent
    facts beyond what this returns.

    Args:
        query: The user's health question, in their own words.
        topic: Optional topic_id to restrict the search to one topic. Leave empty ("") to search
            across all topics - use query_health_topics first if you need to know valid topic_ids.

    Returns:
        A dict with a "results" list. Each result has knowledge_id, topic_id, title, summary,
        hybrid_score, semantic_score, and lexical_score. Empty list means no eligible content
        matched - say so plainly rather than guessing.
    """
    with _client() as client:
        response = client.post(
            "/internal/search-knowledge", json={"query": query, "topic": topic or None, "top_n": 5}
        )
        response.raise_for_status()
        return {"results": response.json()}


def get_knowledge_record(knowledge_id: str) -> dict:
    """Retrieve full structured metadata for one knowledge record, given its knowledge_id (as
    returned by search_knowledge). Use this to double-check a record's review status, source, or
    last-reviewed date before citing it.
    """
    with _client() as client:
        response = client.get(f"/internal/knowledge/{knowledge_id}")
        if response.status_code == 404:
            return {"error": f"Unknown knowledge_id '{knowledge_id}'"}
        response.raise_for_status()
        return response.json()


def get_source_metadata(source_id: str) -> dict:
    """Retrieve provenance details (organization name, URL, active/inactive status) for one
    source_id. Use this when the user asks where an answer's information came from.
    """
    with _client() as client:
        response = client.get(f"/internal/sources/{source_id}")
        if response.status_code == 404:
            return {"error": f"Unknown source_id '{source_id}'"}
        response.raise_for_status()
        return response.json()


def check_content_eligibility(knowledge_id: str) -> dict:
    """Verify whether a specific knowledge record is CURRENTLY eligible to be used as generation
    context (review_status APPROVED, source ACTIVE, content CURRENT). Use this if you're unsure
    whether something search_knowledge returned is still safe to rely on.
    """
    with _client() as client:
        response = client.get(f"/internal/knowledge/{knowledge_id}/eligibility")
        if response.status_code == 404:
            return {"error": f"Unknown knowledge_id '{knowledge_id}'"}
        response.raise_for_status()
        return response.json()


def query_health_topics() -> dict:
    """List every governed women's-health topic available in the knowledge base, with each
    topic's topic_id, name, and parent category. Use this when the user asks what topics are
    covered, or before calling search_knowledge with a specific topic filter.
    """
    with _client() as client:
        response = client.get("/internal/topics")
        response.raise_for_status()
        return {"topics": response.json()}


def find_related_topics(topic_id: str) -> dict:
    """Find other women's-health topics related to the given topic_id, to suggest as
    related-topic follow-ups after answering a question.
    """
    with _client() as client:
        response = client.get(f"/internal/topics/{topic_id}/related")
        response.raise_for_status()
        return {"related_topics": response.json()}
