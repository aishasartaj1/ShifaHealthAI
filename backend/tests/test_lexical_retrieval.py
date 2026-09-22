from src.retrieval.lexical import rank_by_bm25

CORPUS = [
    {
        "knowledge_id": "pcos_1",
        "title": "What PCOS is",
        "summary": "Polycystic ovary syndrome involves insulin resistance and irregular ovulation.",
    },
    {
        "knowledge_id": "menopause_1",
        "title": "What menopause is",
        "summary": "Menopause marks the point periods have stopped permanently.",
    },
    {
        "knowledge_id": "contra_1",
        "title": "Contraception overview",
        "summary": "Birth control methods range from pills to long-acting reversible options.",
    },
]


def test_rank_by_bm25_favors_exact_term_match():
    ranked = rank_by_bm25("PCOS insulin resistance", CORPUS)
    assert ranked[0]["knowledge_id"] == "pcos_1"


def test_rank_by_bm25_empty_corpus_returns_empty():
    assert rank_by_bm25("anything", []) == []


def test_rank_by_bm25_includes_score_field():
    ranked = rank_by_bm25("menopause", CORPUS)
    assert all("score" in r for r in ranked)
    assert ranked[0]["knowledge_id"] == "menopause_1"
