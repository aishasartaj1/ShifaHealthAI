from src.retrieval.semantic import cosine_similarity, rank_by_similarity


def test_cosine_similarity_identical_vectors():
    assert cosine_similarity([1.0, 0.0], [1.0, 0.0]) == 1.0


def test_cosine_similarity_orthogonal_vectors():
    assert cosine_similarity([1.0, 0.0], [0.0, 1.0]) == 0.0


def test_cosine_similarity_opposite_vectors():
    assert cosine_similarity([1.0, 0.0], [-1.0, 0.0]) == -1.0


def test_cosine_similarity_zero_vector_does_not_divide_by_zero():
    assert cosine_similarity([0.0, 0.0], [1.0, 0.0]) == 0.0


def test_rank_by_similarity_orders_by_closeness_to_query():
    query = [1.0, 0.0]
    corpus = [
        {"knowledge_id": "far", "embedding": [0.0, 1.0]},
        {"knowledge_id": "close", "embedding": [0.99, 0.01]},
    ]
    ranked = rank_by_similarity(query, corpus)
    assert [r["knowledge_id"] for r in ranked] == ["close", "far"]


def test_rank_by_similarity_drops_raw_embedding_from_output():
    corpus = [{"knowledge_id": "a", "embedding": [1.0, 0.0], "title": "T"}]
    ranked = rank_by_similarity([1.0, 0.0], corpus)
    assert "embedding" not in ranked[0]
    assert ranked[0]["title"] == "T"
