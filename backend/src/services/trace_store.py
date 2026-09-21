"""In-memory store for agent traces, backing GET /api/admin/agents + /agents/{trace_id}.

Deliberately NOT a BigQuery table: durable, queryable, cross-instance trace storage is exactly
what Phase 7's Pub/Sub -> Dataflow -> BigQuery pipeline is for. Building that now would duplicate
Phase 7's job. This is a documented, bounded, process-local stand-in - traces are lost on
restart and aren't shared across multiple backend instances. Fine for a single-instance DEV demo;
flagged here rather than silently passed off as durable.
"""

from __future__ import annotations

from collections import OrderedDict
from threading import Lock

_MAX_TRACES = 200
_store: OrderedDict[str, dict] = OrderedDict()
_lock = Lock()


def record_trace(trace_id: str, data: dict) -> None:
    with _lock:
        _store[trace_id] = data
        _store.move_to_end(trace_id)
        while len(_store) > _MAX_TRACES:
            _store.popitem(last=False)


def get_trace(trace_id: str) -> dict | None:
    return _store.get(trace_id)


def list_recent_traces(limit: int = 20) -> list[dict]:
    with _lock:
        return list(reversed(list(_store.values())))[:limit]
