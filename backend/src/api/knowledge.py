from __future__ import annotations

from fastapi import APIRouter, HTTPException

from src.config import get_settings
from src.repositories import bigquery as repo

router = APIRouter(prefix="/api", tags=["knowledge"])


@router.get("/knowledge/{knowledge_id}")
def get_knowledge(knowledge_id: str) -> dict:
    settings = get_settings()
    record = repo.get_knowledge_record(repo.get_bigquery_client(), settings.gcp_project_id, knowledge_id)
    if record is None:
        raise HTTPException(status_code=404, detail=f"Unknown knowledge_id '{knowledge_id}'")
    return record


@router.get("/sources/{source_id}")
def get_source(source_id: str) -> dict:
    settings = get_settings()
    record = repo.get_source_record(repo.get_bigquery_client(), settings.gcp_project_id, source_id)
    if record is None:
        raise HTTPException(status_code=404, detail=f"Unknown source_id '{source_id}'")
    return record
