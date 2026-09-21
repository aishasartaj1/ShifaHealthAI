from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Runtime configuration, sourced from environment variables / .env.

    Only Phase 1 fields are defined here. Later phases (BigQuery, Vertex AI,
    Pub/Sub) add their own settings as those integrations land — this stays
    the single place the app reads config from, rather than os.environ calls
    scattered through the codebase.
    """

    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    environment: str = "dev"
    gcp_project_id: str = "shifahealthai"
    gcp_region: str = "us-central1"
    cors_allow_origins: list[str] = ["http://localhost:5173"]

    # Shared secret between backend and agents/ for the /internal/* routes (backend/src/api/internal.py).
    # This is a DEV-appropriate stand-in for real Cloud Run IAM ID-token verification - see the Phase 5
    # entry in docs/DEVLOG.md for why, and docs/BACKLOG.md's Phase 8 tickets for the real replacement.
    internal_api_key: str = "dev-internal-key-change-me"

    # Where the private agents/ service lives (src/services/agent_client.py). In DEV, localhost;
    # in a real deployment, the agents Cloud Run service's private URL.
    agent_service_base_url: str = "http://localhost:8001"

    # Pub/Sub topic interaction events are published to (src/services/pubsub.py), matching
    # infra/terraform/modules/pubsub's google_pubsub_topic name.
    pubsub_topic: str = "shifahealth-events"


@lru_cache
def get_settings() -> Settings:
    return Settings()
