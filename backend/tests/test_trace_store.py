import uuid

from src.services import trace_store


def _fresh_trace_id() -> str:
    return str(uuid.uuid4())


def test_record_and_get_trace_roundtrip():
    trace_id = _fresh_trace_id()
    trace_store.record_trace(trace_id, {"trace_id": trace_id, "question": "test"})
    assert trace_store.get_trace(trace_id) == {"trace_id": trace_id, "question": "test"}


def test_get_trace_missing_returns_none():
    assert trace_store.get_trace(_fresh_trace_id()) is None


def test_list_recent_traces_most_recent_first():
    ids = [_fresh_trace_id() for _ in range(3)]
    for trace_id in ids:
        trace_store.record_trace(trace_id, {"trace_id": trace_id})
    recent = trace_store.list_recent_traces(limit=3)
    recent_ids = [t["trace_id"] for t in recent]
    assert recent_ids.index(ids[-1]) < recent_ids.index(ids[0])


def test_list_recent_traces_respects_limit():
    for _ in range(5):
        trace_id = _fresh_trace_id()
        trace_store.record_trace(trace_id, {"trace_id": trace_id})
    assert len(trace_store.list_recent_traces(limit=2)) == 2
