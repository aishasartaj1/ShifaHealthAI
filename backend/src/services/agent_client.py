"""HTTP client for backend -> the private agents/ Cloud Run service (architecture.md's Service
Topology). Not wired to a public route yet - POST /api/chat (Phase 6) is what will call this;
Phase 5's job was proving the agent service itself works, which agents/tests/ and a manual
end-to-end run (see docs/DEVLOG.md) already did.

In DEV this points at http://localhost:8001. In a real deployment it would point at the agents
service's private Cloud Run URL, with a Google-signed ID token attached as the Authorization
header (Cloud Run enforces this for private-ingress services via IAM roles/run.invoker) - that
part isn't implemented yet since there's no real Cloud Run deployment until Phase 8.
"""

from __future__ import annotations

import httpx

from src.config import get_settings


class AgentClient:
    def __init__(self, base_url: str | None = None, timeout: float = 60.0) -> None:
        settings = get_settings()
        self._base_url = base_url or settings.agent_service_base_url
        self._timeout = timeout

    def invoke(self, message: str, user_id: str, session_id: str | None = None) -> dict:
        with httpx.Client(base_url=self._base_url, timeout=self._timeout) as client:
            response = client.post(
                "/invoke", json={"message": message, "user_id": user_id, "session_id": session_id}
            )
            response.raise_for_status()
            return response.json()
