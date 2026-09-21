from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    environment: str = "dev"
    gcp_project_id: str = "shifahealthai"
    gcp_region: str = "us-central1"
    gemini_model: str = "gemini-2.5-flash"

    # Where backend's /internal/* API lives, and the shared secret it expects.
    # See backend/src/api/internal.py's module docstring for why this is a shared secret rather
    # than real IAM-based service identity in DEV.
    backend_base_url: str = "http://localhost:8000"
    internal_api_key: str = "dev-internal-key-change-me"


@lru_cache
def get_settings() -> Settings:
    return Settings()
