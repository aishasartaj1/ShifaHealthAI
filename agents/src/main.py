"""FastAPI wrapper around the ADK agent. Cloud Run (and every other host ADK doesn't already
provide a server for) needs an HTTP entrypoint; this is deliberately minimal — one route to run
the agent, one health check — rather than adopting ADK's own dev-server tooling (`adk web`,
`adk api_server`), which is aimed at local development/demos, not a private Cloud Run service
that only backend/src/services/agent_client.py ever calls.
"""

from __future__ import annotations

import time
from contextvars import ContextVar

from fastapi import FastAPI
from google.adk.runners import InMemoryRunner
from google.genai import types
from pydantic import BaseModel

from src.agent import build_agent
from src.config import get_settings
from src.trace import TraceRecorder

settings = get_settings()

app = FastAPI(
    title="ShifaHealth AI Agent Service",
    description="Standalone ADK agent runtime — private, invoked only by the backend service.",
    version="0.1.0",
)

APP_NAME = "shifahealth_agents"

# The Runner (and the InMemorySessionService it owns) is a MODULE-LEVEL SINGLETON, built once,
# not per-request. A fresh Runner per request was the first version of this file's actual bug:
# InMemorySessionService's state lives in that Runner instance, so recreating it every request
# silently wiped session history every time - reusing the same session_id did nothing. One
# process-lifetime Runner is what makes multi-turn conversations actually persist (within this
# one process; a real multi-replica deployment would need a shared session backend instead of
# in-memory - out of scope for this DEV demo, and the same "no long-term memory" boundary the
# plan already draws in Section 30).
#
# Per-request trace isolation still needs solving separately, since the Agent object (and its
# tool callbacks) is now shared across requests too. A ContextVar does this correctly: each
# FastAPI request runs in its own asyncio Task, and a ContextVar set inside that Task is
# invisible to other concurrent Tasks - exactly the isolation a per-request trace needs.
_current_trace: ContextVar[TraceRecorder | None] = ContextVar("current_trace", default=None)


def _before_tool_callback(tool, args, tool_context):
    trace = _current_trace.get()
    if trace is not None:
        trace.before_tool(tool, args, tool_context)


def _after_tool_callback(tool, args, tool_context, result):
    trace = _current_trace.get()
    if trace is not None:
        trace.after_tool(tool, args, tool_context, result)


_agent = build_agent(before_tool_callback=_before_tool_callback, after_tool_callback=_after_tool_callback)
_runner = InMemoryRunner(agent=_agent, app_name=APP_NAME)


@app.get("/health")
def health() -> dict:
    return {"status": "ok", "service": "shifahealth-agents", "environment": settings.environment}


class InvokeRequest(BaseModel):
    message: str
    user_id: str = "anonymous"
    session_id: str | None = None


class InvokeResponse(BaseModel):
    response: str
    trace: dict


@app.post("/invoke", response_model=InvokeResponse)
async def invoke(body: InvokeRequest) -> InvokeResponse:
    trace = TraceRecorder()
    token = _current_trace.set(trace)
    try:
        session_id = body.session_id or body.user_id
        session = await _runner.session_service.get_session(
            app_name=APP_NAME, user_id=body.user_id, session_id=session_id
        )
        if session is None:
            session = await _runner.session_service.create_session(
                app_name=APP_NAME, user_id=body.user_id, session_id=session_id
            )

        message = types.Content(role="user", parts=[types.Part(text=body.message)])
        started_at = time.monotonic()
        response_text_parts: list[str] = []

        async for event in _runner.run_async(user_id=body.user_id, session_id=session.id, new_message=message):
            if event.content and event.content.parts:
                for part in event.content.parts:
                    if part.text:
                        response_text_parts.append(part.text)

        total_latency_ms = round((time.monotonic() - started_at) * 1000, 1)

        return InvokeResponse(
            response="".join(response_text_parts).strip(),
            trace={"tool_calls": trace.tool_calls, "total_latency_ms": total_latency_ms},
        )
    finally:
        _current_trace.reset(token)
