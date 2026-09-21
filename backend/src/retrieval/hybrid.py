"""Merge + rerank semantic and lexical candidates into one ranked list.

Pure functions only, deliberately — no BigQuery/Vertex AI calls here, so the merge/rerank logic
(the actual interesting part of "hybrid RAG") is unit-testable with plain dicts. semantic.py and
lexical.py own the IO; this module just combines whatever ranked lists they hand it.
"""

from __future__ import annotations


def normalize_scores(results: list[dict]) -> list[dict]:
    """Min-max normalize `score` to [0, 1] so semantic (cosine, ~[0,1]) and lexical (BM25,
    unbounded) scores are comparable before combining. All-equal scores normalize to 1.0 each
    (treated as equally relevant) rather than dividing by zero."""
    if not results:
        return []
    scores = [r["score"] for r in results]
    lo, hi = min(scores), max(scores)
    if hi == lo:
        return [{**r, "score": 1.0} for r in results]
    return [{**r, "score": (r["score"] - lo) / (hi - lo)} for r in results]


def merge_and_rerank(
    semantic_results: list[dict],
    lexical_results: list[dict],
    semantic_weight: float = 0.6,
    lexical_weight: float = 0.4,
    top_n: int = 5,
) -> list[dict]:
    """Combine two ranked candidate lists (each a list of dicts with `knowledge_id` + `score`)
    into one, keyed by knowledge_id. A candidate appearing in only one list gets 0 for the other
    side's score rather than being dropped - showing up in either signal is still a candidate.

    Returns dicts with `hybrid_score`, `semantic_score`, `lexical_score`, plus whatever other
    fields the input rows carried (topic_id, title, summary, ...), sorted by hybrid_score desc,
    truncated to top_n.
    """
    norm_semantic = {r["knowledge_id"]: r["score"] for r in normalize_scores(semantic_results)}
    norm_lexical = {r["knowledge_id"]: r["score"] for r in normalize_scores(lexical_results)}

    metadata_by_id = {r["knowledge_id"]: r for r in lexical_results}
    metadata_by_id.update({r["knowledge_id"]: r for r in semantic_results})  # semantic wins on conflicting metadata

    merged = []
    for knowledge_id in metadata_by_id:
        semantic_score = norm_semantic.get(knowledge_id, 0.0)
        lexical_score = norm_lexical.get(knowledge_id, 0.0)
        base = {k: v for k, v in metadata_by_id[knowledge_id].items() if k != "score"}
        merged.append(
            {
                **base,
                "hybrid_score": semantic_weight * semantic_score + lexical_weight * lexical_score,
                "semantic_score": semantic_score,
                "lexical_score": lexical_score,
            }
        )

    merged.sort(key=lambda r: r["hybrid_score"], reverse=True)
    return merged[:top_n]
