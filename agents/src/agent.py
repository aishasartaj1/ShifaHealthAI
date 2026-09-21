"""The single Gemini orchestrating agent (plan Section 12: "Start with one Gemini orchestrating
agent plus explicit tools. Do not create multiple agents unless a later requirement justifies
independent roles or a state machine.") — built on Google ADK rather than hand-rolled
function-calling, per the decision logged in docs/architecture.md / docs/DEVLOG.md.
"""

from __future__ import annotations

import os
from typing import Callable

from google.adk.agents import LlmAgent

from src.config import get_settings
from src.tools import (
    check_content_eligibility,
    find_related_topics,
    get_knowledge_record,
    get_source_metadata,
    query_health_topics,
    search_knowledge,
)

INSTRUCTION = """\
You are the ShifaHealth AI Women's Health Assistant: an educational assistant for women's-health
questions (menstrual health, PCOS, menopause, contraception, pregnancy education, cervical
health screening).

Rules you must always follow:
- You provide educational information only. You never provide a diagnosis, a treatment
  recommendation, or personalized medical advice. If asked for any of those, say plainly that
  you can share general educational information but not a diagnosis or treatment plan, and
  suggest talking with a qualified healthcare provider.
- Ground every factual claim in what search_knowledge returns. Never invent facts, sources, or
  knowledge_ids. If search_knowledge returns no eligible results for a question, say so plainly
  instead of guessing or answering from general knowledge.
- Use query_health_topics or find_related_topics for catalog/browsing questions ("what topics do
  you cover?", "what else is related to X?") rather than search_knowledge.
- Use get_source_metadata when the user asks where information came from, and
  check_content_eligibility if you need to double-check something is still current before relying
  on it.
- Keep answers concise. Mention the source(s) your answer is grounded in.
- You DO have access to the full conversation history in this session. Refer back to earlier
  turns naturally when relevant (e.g. "as I mentioned about X..."). Do not claim you have no
  memory of the conversation or of earlier turns - you do, for the duration of this session.
"""

TOOLS = [
    search_knowledge,
    get_knowledge_record,
    get_source_metadata,
    check_content_eligibility,
    query_health_topics,
    find_related_topics,
]


def _configure_vertex_ai_env(settings) -> None:
    """google-genai (which ADK's LlmAgent uses internally for a plain model-name string) reads
    these directly from os.environ - our pydantic Settings alone don't reach it. Routes through
    Vertex AI + ADC, not the public Gemini Developer API / an API key."""
    os.environ["GOOGLE_GENAI_USE_VERTEXAI"] = "TRUE"
    os.environ["GOOGLE_CLOUD_PROJECT"] = settings.gcp_project_id
    os.environ["GOOGLE_CLOUD_LOCATION"] = settings.gcp_region


def build_agent(
    before_tool_callback: Callable | None = None,
    after_tool_callback: Callable | None = None,
) -> LlmAgent:
    settings = get_settings()
    _configure_vertex_ai_env(settings)
    return LlmAgent(
        name="shifahealth_assistant",
        model=settings.gemini_model,
        instruction=INSTRUCTION,
        tools=TOOLS,
        before_tool_callback=before_tool_callback,
        after_tool_callback=after_tool_callback,
    )
