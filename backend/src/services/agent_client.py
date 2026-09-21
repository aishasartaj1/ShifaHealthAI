"""HTTP client for backend -> the private agents/ Cloud Run service (architecture.md's Service
Topology).

In DEV this points at http://localhost:8001 and calls unauthenticated (there's no real Cloud Run
IAM boundary between two local processes). Deployed, agents has `allow_unauthenticated = false`
with only backend's service account granted `roles/run.invoker` - Cloud Run enforces that at the
platform level, before the request ever reaches agents' application code, so a plain HTTP POST
with no credentials gets a 404 from Cloud Run's own front door (this was caught by actually
deploying and testing, not anticipated in advance - see docs/DEVLOG.md's Phase 8 entry). Same
fetch_id_token pattern as agents/src/tools.py uses for the reverse direction: mint an ID token
when ambient service-account credentials support it, fall back to no token when they don't
(local dev, human ADC credentials).
"""

from __future__ import annotations

import logging

import httpx
from google.auth.transport import requests as google_auth_requests
from google.oauth2 import id_token as google_id_token

from src.config import get_settings

logger = logging.getLogger(__name__)


def _auth_headers(base_url: str, environment: str) -> dict[str, str]:
    if environment == "dev":
        # Skip the attempt entirely rather than let it fail slowly: local ADC (a human's
        # credentials) can't mint an ID token, and discovering that takes several seconds per
        # call (multiple credential sources tried before giving up) - a real cost noticed while
        # testing this against the live deployment, not a hypothetical one.
        return {}
    try:
        token = google_id_token.fetch_id_token(google_auth_requests.Request(), base_url)
        return {"Authorization": f"Bearer {token}"}
    except Exception:
        logger.warning("Failed to mint an ID token for calling agents; request will likely be rejected.")
        return {}


class AgentClient:
    def __init__(self, base_url: str | None = None, timeout: float = 60.0) -> None:
        settings = get_settings()
        self._base_url = base_url or settings.agent_service_base_url
        self._timeout = timeout

    def invoke(self, message: str, user_id: str, session_id: str | None = None) -> dict:
        settings = get_settings()
        with httpx.Client(
            base_url=self._base_url,
            headers=_auth_headers(self._base_url, settings.environment),
            timeout=self._timeout,
        ) as client:
            response = client.post(
                "/invoke", json={"message": message, "user_id": user_id, "session_id": session_id}
            )
            response.raise_for_status()
            return response.json()
