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


@lru_cache
def get_settings() -> Settings:
    return Settings()
