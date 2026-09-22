from eval_retrieval import hit_at_k


def test_hit_at_k_true_when_any_expected_id_in_top_k():
    results = [{"knowledge_id": "a"}, {"knowledge_id": "b"}, {"knowledge_id": "c"}]
    assert hit_at_k(results, ["b"], k=5) is True


def test_hit_at_k_false_when_expected_id_outside_top_k():
    results = [{"knowledge_id": "a"}, {"knowledge_id": "b"}, {"knowledge_id": "c"}]
    assert hit_at_k(results, ["c"], k=2) is False


def test_hit_at_k_false_on_empty_results():
    assert hit_at_k([], ["a"], k=5) is False
