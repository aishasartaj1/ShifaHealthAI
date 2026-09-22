"""Internal API — the HTTP surface backing the agents/ ADK service's six tools (Section 12 of
the plan). Not part of the public-facing API (Section 19); the frontend never calls these.

Two auth mechanisms, checked in order:

1. A Google-issued ID token (`Authorization: Bearer <token>`), verified against Google's public
   certs and checked to belong to exactly the agents service account. This is real
   service-to-service identity - when deployed, agents/src/tools.py mints one of these per request
   (see that file) using Cloud Run's ambient service-account credentials, with `audience` set to
   backend's own public URL. Cloud Run's IAM (backend has public ingress, so there's no
   private-ingress boundary to lean on the way there is for backend -> agents) plays no role here;
   this check is what actually enforces "only the agents service may call /internal/*".
2. A shared-secret header (`X-Internal-Api-Key`), checked only when no Bearer token is present -
   the local-dev fallback, since a local `agents/` process has no real Cloud Run identity to mint
   an ID token with (fetch_id_token raises for a human's ADC credentials, not a service account).

See docs/DEVLOG.md's Phase 5 and Phase 8 entries for why it took two passes to get here.
"""

from __future__ import annotations

from fastapi import APIRouter, Depends, Header, HTTPException
from google.auth.transport import requests as google_auth_requests
from google.oauth2 import id_token as google_id_token
from pydantic import BaseModel

from src.config import get_settings
from src.repositories import bigquery as repo
from src.retrieval.search import search_knowledge
from src.services.vertex_ai import get_genai_client

router = APIRouter(prefix="/internal", tags=["internal"])


def _verify_id_token(token: str, settings) -> bool:
    """True only if `token` is a Google-signed ID token minted for exactly this backend's
    audience, by exactly the agents service account. Any other failure (bad signature, wrong
    audience, unconfigured settings) returns False rather than raising - the caller falls back
    to the shared-secret check."""
    if not settings.public_base_url or not settings.agents_service_account_email:
        return False
    try:
        claims = google_id_token.verify_oauth2_token(
            token, google_auth_requests.Request(), audience=settings.public_base_url
        )
    except Exception:
        return False
    return claims.get("email") == settings.agents_service_account_email


def require_internal_caller(
    authorization: str = Header(default=""), x_internal_api_key: str = Header(default="")
) -> None:
    settings = get_settings()

    if authorization.startswith("Bearer "):
        token = authorization.removeprefix("Bearer ")
        if _verify_id_token(token, settings):
            return
        raise HTTPException(status_code=401, detail="Invalid ID token")

    if x_internal_api_key and x_internal_api_key == settings.internal_api_key:
        return

    raise HTTPException(status_code=401, detail="Missing or invalid caller credentials")


class SearchKnowledgeRequest(BaseModel):
    query: str
    topic: str | None = None
    top_n: int = 5


@router.post("/search-knowledge", dependencies=[Depends(require_internal_caller)])
def search_knowledge_route(body: SearchKnowledgeRequest) -> list[dict]:
    settings = get_settings()
    bq_client = repo.get_bigquery_client()
    genai_client = get_genai_client()
    return search_knowledge(
        genai_client, bq_client, settings.gcp_project_id, body.query, top_n=body.top_n, topic=body.topic
    )


@router.get("/knowledge/{knowledge_id}", dependencies=[Depends(require_internal_caller)])
def get_knowledge_record_route(knowledge_id: str) -> dict:
    settings = get_settings()
    record = repo.get_knowledge_record(repo.get_bigquery_client(), settings.gcp_project_id, knowledge_id)
    if record is None:
        raise HTTPException(status_code=404, detail=f"Unknown knowledge_id '{knowledge_id}'")
    return record


@router.get("/sources/{source_id}", dependencies=[Depends(require_internal_caller)])
def get_source_metadata_route(source_id: str) -> dict:
    settings = get_settings()
    record = repo.get_source_record(repo.get_bigquery_client(), settings.gcp_project_id, source_id)
    if record is None:
        raise HTTPException(status_code=404, detail=f"Unknown source_id '{source_id}'")
    return record


@router.get("/knowledge/{knowledge_id}/eligibility", dependencies=[Depends(require_internal_caller)])
def check_content_eligibility_route(knowledge_id: str) -> dict:
    settings = get_settings()
    eligible = repo.check_eligibility(repo.get_bigquery_client(), settings.gcp_project_id, knowledge_id)
    if eligible is None:
        raise HTTPException(status_code=404, detail=f"Unknown knowledge_id '{knowledge_id}'")
    return {"knowledge_id": knowledge_id, "ai_eligible": eligible}


@router.get("/topics", dependencies=[Depends(require_internal_caller)])
def query_health_topics_route() -> list[dict]:
    settings = get_settings()
    return repo.list_topics(repo.get_bigquery_client(), settings.gcp_project_id)


@router.get("/topics/{topic_id}/related", dependencies=[Depends(require_internal_caller)])
def find_related_topics_route(topic_id: str, limit: int = 3) -> list[dict]:
    settings = get_settings()
    return repo.list_related_topics(repo.get_bigquery_client(), settings.gcp_project_id, topic_id, limit=limit)
