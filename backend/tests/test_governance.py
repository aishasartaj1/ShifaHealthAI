from src.retrieval.governance import filter_eligible


def test_filter_eligible_keeps_only_eligible_candidates():
    candidates = [{"knowledge_id": "a"}, {"knowledge_id": "b"}, {"knowledge_id": "c"}]
    result = filter_eligible(candidates, eligible_ids={"a", "c"})
    assert [c["knowledge_id"] for c in result] == ["a", "c"]


def test_filter_eligible_preserves_input_order():
    candidates = [{"knowledge_id": "c"}, {"knowledge_id": "a"}, {"knowledge_id": "b"}]
    result = filter_eligible(candidates, eligible_ids={"a", "b", "c"})
    assert [c["knowledge_id"] for c in result] == ["c", "a", "b"]


def test_filter_eligible_empty_eligible_set_drops_everything():
    candidates = [{"knowledge_id": "a"}, {"knowledge_id": "b"}]
    assert filter_eligible(candidates, eligible_ids=set()) == []


def test_filter_eligible_rejects_stale_or_expired_candidate():
    # simulates the drift case: a candidate the vector index still has, that BigQuery's
    # CURRENT governance state no longer considers eligible (see docs/governance.md).
    candidates = [{"knowledge_id": "know_mc_007"}, {"knowledge_id": "know_mc_001"}]
    result = filter_eligible(candidates, eligible_ids={"know_mc_001"})
    assert [c["knowledge_id"] for c in result] == ["know_mc_001"]
