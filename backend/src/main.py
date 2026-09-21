from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from src.api.admin import router as admin_router
from src.api.chat import router as chat_router
from src.api.internal import router as internal_router
from src.api.knowledge import router as knowledge_router
from src.api.topics import router as topics_router
from src.config import get_settings

settings = get_settings()

app = FastAPI(
    title="ShifaHealth AI Backend",
    description="Governed agentic women's health knowledge platform — API layer.",
    version="0.1.0",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_allow_origins,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(internal_router)
app.include_router(chat_router)
app.include_router(topics_router)
app.include_router(knowledge_router)
app.include_router(admin_router)


@app.get("/health")
def health() -> dict:
    return {
        "status": "ok",
        "service": "shifahealth-backend",
        "environment": settings.environment,
    }
