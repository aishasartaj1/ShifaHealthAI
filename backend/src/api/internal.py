"""Internal API — the HTTP surface backing the agents/ ADK service's six tools (Section 12 of
the plan). Not part of the public-facing API (Section 19); the frontend never calls these.

Auth here is a shared-secret header (`X-Internal-Api-Key`), checked against
`settings.internal_api_key`. This is a deliberate DEV-appropriate simplification, not real
service-to-service identity: backend has public Cloud Run ingress (the frontend needs to reach
it), so a caller-identity check based on Cloud Run IAM (which only applies to *private* ingress)
isn't available here the way it is for backend -> agents. Production would either move this
under IAM-verified private ingress or verify the caller's Google-issued ID token directly
(google.oauth2.id_token.verify_oauth2_token). See docs/DEVLOG.md's Phase 5 entry and
docs/BACKLOG.md's Phase 8 tickets.
"""

from __future__ import annotations

from fastapi import APIRouter, Depends, Header, HTTPException
from google.cloud import bigquery
from pydantic import BaseModel

from src.config import get_settings
from src.repositories import bigquery as repo
from src.retrieval.search import search_knowledge
from src.services.vertex_ai import get_genai_client

router = APIRouter(prefix="/internal", tags=["internal"])


def require_internal_api_key(x_internal_api_key: str = Header(default="")) -> None:
    settings = get_settings()
    if x_internal_api_key != settings.internal_api_key:
        raise HTTPException(status_code=401, detail="Invalid or missing X-Internal-Api-Key")


class SearchKnowledgeRequest(BaseModel):
    query: str
    topic: str | None = None
    top_n: int = 5


@router.post("/search-knowledge", dependencies=[Depends(require_internal_api_key)])
def search_knowledge_route(body: SearchKnowledgeRequest) -> list[dict]:
    settings = get_settings()
    bq_client = repo.get_bigquery_client()
    genai_client = get_genai_client()
    return search_knowledge(
        genai_client, bq_client, settings.gcp_project_id, body.query, top_n=body.top_n, topic=body.topic
    )


@router.get("/knowledge/{knowledge_id}", dependencies=[Depends(require_internal_api_key)])
def get_knowledge_record_route(knowledge_id: str) -> dict:
    settings = get_settings()
    record = repo.get_knowledge_record(repo.get_bigquery_client(), settings.gcp_project_id, knowledge_id)
    if record is None:
        raise HTTPException(status_code=404, detail=f"Unknown knowledge_id '{knowledge_id}'")
    return record


@router.get("/sources/{source_id}", dependencies=[Depends(require_internal_api_key)])
def get_source_metadata_route(source_id: str) -> dict:
    settings = get_settings()
    record = repo.get_source_record(repo.get_bigquery_client(), settings.gcp_project_id, source_id)
    if record is None:
        raise HTTPException(status_code=404, detail=f"Unknown source_id '{source_id}'")
    return record


@router.get("/knowledge/{knowledge_id}/eligibility", dependencies=[Depends(require_internal_api_key)])
def check_content_eligibility_route(knowledge_id: str) -> dict:
    settings = get_settings()
    eligible = repo.check_eligibility(repo.get_bigquery_client(), settings.gcp_project_id, knowledge_id)
    if eligible is None:
        raise HTTPException(status_code=404, detail=f"Unknown knowledge_id '{knowledge_id}'")
    return {"knowledge_id": knowledge_id, "ai_eligible": eligible}


@router.get("/topics", dependencies=[Depends(require_internal_api_key)])
def query_health_topics_route() -> list[dict]:
    settings = get_settings()
    return repo.list_topics(repo.get_bigquery_client(), settings.gcp_project_id)


@router.get("/topics/{topic_id}/related", dependencies=[Depends(require_internal_api_key)])
def find_related_topics_route(topic_id: str, limit: int = 3) -> list[dict]:
    settings = get_settings()
    return repo.list_related_topics(repo.get_bigquery_client(), settings.gcp_project_id, topic_id, limit=limit)
