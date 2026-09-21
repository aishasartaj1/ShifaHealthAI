"""Admin/observability endpoints backing the AI/Data Operations Console (plan Section 4.2)."""

from __future__ import annotations

from fastapi import APIRouter, HTTPException

from src.config import get_settings
from src.repositories import bigquery as repo
from src.services.trace_store import get_trace, list_recent_traces

router = APIRouter(prefix="/api/admin", tags=["admin"])


@router.get("/quality")
def quality() -> dict:
    settings = get_settings()
    return repo.get_quality_summary(repo.get_bigquery_client(), settings.gcp_project_id)


@router.get("/agents")
def list_agent_traces(limit: int = 20) -> list[dict]:
    return list_recent_traces(limit=limit)


@router.get("/agents/{trace_id}")
def get_agent_trace(trace_id: str) -> dict:
    trace = get_trace(trace_id)
    if trace is None:
        raise HTTPException(status_code=404, detail=f"Unknown trace_id '{trace_id}'")
    return trace
