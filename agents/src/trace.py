"""Agent observability, per docs/architecture.md: tool names, args, result summaries, and
latency - never raw chain-of-thought (the LLM's own reasoning text never enters this trace).

Wired into an LlmAgent via before_tool_callback/after_tool_callback (see agent.py). ADK calls
these sequentially per tool invocation within one turn, so a simple stack correlates each
before/after pair correctly without needing an explicit call ID from ADK.
"""

from __future__ import annotations

import time


def summarize_result(result: object) -> dict:
    """Reduce a tool's raw return value to a small, safe summary - counts, IDs, and error flags,
    never full record content (titles/summaries), matching the plan's "governance rejected: 2"
    style observability. knowledge_ids are included (not just a count) because backend/src/api/
    chat.py needs them to build real source cards for the consumer response - an ID is a
    structured reference, not raw content or reasoning, so this doesn't compromise "no raw
    chain-of-thought"."""
    if isinstance(result, dict):
        if isinstance(result.get("results"), list):
            return {
                "candidate_count": len(result["results"]),
                "candidate_knowledge_ids": [r.get("knowledge_id") for r in result["results"] if isinstance(r, dict)],
            }
        if isinstance(result.get("topics"), list):
            return {"topic_count": len(result["topics"])}
        if isinstance(result.get("related_topics"), list):
            return {"related_count": len(result["related_topics"])}
        if "error" in result:
            return {"error": result["error"]}
        return {"keys": sorted(result.keys())}
    return {"value": str(result)[:200]}


class TraceRecorder:
    def __init__(self) -> None:
        self.tool_calls: list[dict] = []
        self._pending: list[dict] = []

    def before_tool(self, tool, args, tool_context) -> None:
        self._pending.append({"tool": tool.name, "args": dict(args), "_started_at": time.monotonic()})
        return None  # never short-circuits the real tool call

    def after_tool(self, tool, args, tool_context, result) -> None:
        entry = self._pending.pop()
        started_at = entry.pop("_started_at")
        entry["latency_ms"] = round((time.monotonic() - started_at) * 1000, 1)
        entry["result_summary"] = summarize_result(result)
        self.tool_calls.append(entry)
        return None  # never modifies the real result
