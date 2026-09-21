from functools import lru_cache

from google import genai

from src.config import get_settings


@lru_cache
def get_genai_client() -> genai.Client:
    settings = get_settings()
    return genai.Client(vertexai=True, project=settings.gcp_project_id, location=settings.gcp_region)
