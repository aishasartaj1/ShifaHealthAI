from src.retrieval.hybrid import merge_and_rerank, normalize_scores


def test_normalize_scores_min_max():
    results = [{"knowledge_id": "a", "score": 0.0}, {"knowledge_id": "b", "score": 5.0}, {"knowledge_id": "c", "score": 10.0}]
    normalized = normalize_scores(results)
    assert normalized[0]["score"] == 0.0
    assert normalized[1]["score"] == 0.5
    assert normalized[2]["score"] == 1.0


def test_normalize_scores_all_equal_avoids_divide_by_zero():
    results = [{"knowledge_id": "a", "score": 3.0}, {"knowledge_id": "b", "score": 3.0}]
    normalized = normalize_scores(results)
    assert all(r["score"] == 1.0 for r in normalized)


def test_normalize_scores_empty():
    assert normalize_scores([]) == []


def test_merge_and_rerank_sorts_by_hybrid_score():
    semantic_results = [{"knowledge_id": "a", "score": 1.0}, {"knowledge_id": "b", "score": 0.0}]
    lexical_results = [{"knowledge_id": "a", "score": 0.0}, {"knowledge_id": "b", "score": 1.0}]
    merged = merge_and_rerank(semantic_results, lexical_results, semantic_weight=1.0, lexical_weight=0.0)
    assert [r["knowledge_id"] for r in merged] == ["a", "b"]


def test_merge_and_rerank_respects_weights():
    semantic_results = [{"knowledge_id": "a", "score": 1.0}, {"knowledge_id": "b", "score": 0.0}]
    lexical_results = [{"knowledge_id": "a", "score": 0.0}, {"knowledge_id": "b", "score": 1.0}]
    # flip the weighting - now b should win
    merged = merge_and_rerank(semantic_results, lexical_results, semantic_weight=0.0, lexical_weight=1.0)
    assert merged[0]["knowledge_id"] == "b"


def test_merge_and_rerank_keeps_candidates_from_only_one_side():
    semantic_results = [{"knowledge_id": "only_semantic", "score": 1.0}]
    lexical_results = [{"knowledge_id": "only_lexical", "score": 1.0}]
    merged = merge_and_rerank(semantic_results, lexical_results, top_n=10)
    ids = {r["knowledge_id"] for r in merged}
    assert ids == {"only_semantic", "only_lexical"}
    only_semantic = next(r for r in merged if r["knowledge_id"] == "only_semantic")
    assert only_semantic["lexical_score"] == 0.0


def test_merge_and_rerank_respects_top_n():
    semantic_results = [{"knowledge_id": str(i), "score": float(i)} for i in range(10)]
    merged = merge_and_rerank(semantic_results, [], top_n=3)
    assert len(merged) == 3
    assert merged[0]["knowledge_id"] == "9"


def test_merge_and_rerank_carries_through_metadata():
    semantic_results = [{"knowledge_id": "a", "score": 1.0, "topic_id": "pcos", "title": "T"}]
    merged = merge_and_rerank(semantic_results, [])
    assert merged[0]["topic_id"] == "pcos"
    assert merged[0]["title"] == "T"
    assert "score" not in merged[0]  # replaced by hybrid_score/semantic_score/lexical_score
