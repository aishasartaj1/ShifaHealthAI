"""Retrieval evaluation: run scripts/retrieval_benchmark.json's question set against the real
semantic-only, lexical-only, and hybrid retrieval code and report hit@5 / no-result / governance-
rejection rates for each - see docs/rag-design.md's "Retrieval evaluation" section for why this
exists (making the semantic+lexical hybrid choice evidence-based rather than assumed) and where
these results get written up.

    python scripts/eval_retrieval.py --project shifahealthai

Deliberately imports backend/src/retrieval's actual modules rather than reimplementing scoring
here - an evaluation of logic that isn't the logic actually running in production would be
worthless, and this project's retrieval code is already exactly the pure-functions-plus-thin-IO
shape that makes reusing it straightforward (see hybrid.py, governance.py).
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

_BACKEND_SRC = Path(__file__).resolve().parents[1] / "backend"
if str(_BACKEND_SRC) not in sys.path:
    sys.path.insert(0, str(_BACKEND_SRC))

from google import genai  # noqa: E402
from google.cloud import bigquery  # noqa: E402

from src.retrieval import governance, hybrid, lexical, semantic  # noqa: E402

BENCHMARK_PATH = Path(__file__).resolve().parent / "retrieval_benchmark.json"
TOP_K = 5


def load_benchmark() -> list[dict]:
    return json.loads(BENCHMARK_PATH.read_text(encoding="utf-8"))


def hit_at_k(results: list[dict], expected_ids: list[str], k: int = TOP_K) -> bool:
    top_ids = {r["knowledge_id"] for r in results[:k]}
    return bool(top_ids & set(expected_ids))


def run_case(
    genai_client: genai.Client,
    bq_client: bigquery.Client,
    project: str,
    eligible_ids: set[str],
    case: dict,
) -> dict:
    query = case["question"]

    semantic_raw = semantic.semantic_search(genai_client, bq_client, project, query, top_n=10)
    lexical_raw = lexical.lexical_search(bq_client, project, query, top_n=10)
    hybrid_raw = hybrid.merge_and_rerank(semantic_raw, lexical_raw, top_n=10)

    semantic_governed = governance.filter_eligible(semantic_raw, eligible_ids)
    lexical_governed = governance.filter_eligible(lexical_raw, eligible_ids)
    hybrid_governed = governance.filter_eligible(hybrid_raw, eligible_ids)

    expected = case["expected_knowledge_ids"]
    result = {
        "id": case["id"],
        "type": case["type"],
        "style": case["style"],
        "semantic_hit": hit_at_k(semantic_governed, expected),
        "lexical_hit": hit_at_k(lexical_governed, expected),
        "hybrid_hit": hit_at_k(hybrid_governed, expected),
        "semantic_empty": len(semantic_governed) == 0,
        "lexical_empty": len(lexical_governed) == 0,
        "hybrid_empty": len(hybrid_governed) == 0,
    }

    if case["type"] == "governance_reject":
        excluded_id = case["excluded_knowledge_id"]
        raw_ids = {r["knowledge_id"] for r in hybrid_raw[:TOP_K]}
        governed_ids = {r["knowledge_id"] for r in hybrid_governed[:TOP_K]}
        result["excluded_id_was_a_raw_candidate"] = excluded_id in raw_ids
        result["excluded_id_correctly_dropped"] = excluded_id not in governed_ids

    return result


def summarize(results: list[dict]) -> None:
    grounded = [r for r in results if r["type"] == "grounded"]
    governance_cases = [r for r in results if r["type"] == "governance_reject"]

    print(f"\n{'case':<10} {'style':<10} {'semantic':<10} {'lexical':<10} {'hybrid':<10}")
    for r in grounded:
        print(
            f"{r['id']:<10} {r['style']:<10} "
            f"{'hit' if r['semantic_hit'] else 'miss':<10} "
            f"{'hit' if r['lexical_hit'] else 'miss':<10} "
            f"{'hit' if r['hybrid_hit'] else 'miss':<10}"
        )

    def rate(rows: list[dict], key: str) -> str:
        if not rows:
            return "n/a"
        return f"{sum(r[key] for r in rows)}/{len(rows)}"

    print("\n--- Grounded questions (hit@5), by style ---")
    for style in ("semantic", "lexical"):
        rows = [r for r in grounded if r["style"] == style]
        print(
            f"{style:<10} n={len(rows):<3} "
            f"semantic-only={rate(rows, 'semantic_hit')}  "
            f"lexical-only={rate(rows, 'lexical_hit')}  "
            f"hybrid={rate(rows, 'hybrid_hit')}"
        )

    print("\n--- Grounded questions (hit@5), overall ---")
    print(
        f"n={len(grounded)}  "
        f"semantic-only={rate(grounded, 'semantic_hit')}  "
        f"lexical-only={rate(grounded, 'lexical_hit')}  "
        f"hybrid={rate(grounded, 'hybrid_hit')}"
    )

    print("\n--- No-result rate (governed top-5 empty) ---")
    print(
        f"semantic-only={rate(grounded, 'semantic_empty')}  "
        f"lexical-only={rate(grounded, 'lexical_empty')}  "
        f"hybrid={rate(grounded, 'hybrid_empty')}"
    )

    print("\n--- Governance-rejection cases ---")
    for r in governance_cases:
        print(
            f"{r['id']:<10} was a raw candidate: {r['excluded_id_was_a_raw_candidate']!s:<6} "
            f"correctly dropped: {r['excluded_id_correctly_dropped']!s:<6}"
        )
    correctly_dropped = sum(r["excluded_id_correctly_dropped"] for r in governance_cases)
    print(f"governance-rejection rate: {correctly_dropped}/{len(governance_cases)}")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--project", default="shifahealthai")
    parser.add_argument("--region", default="us-central1")
    args = parser.parse_args()

    bq_client = bigquery.Client(project=args.project)
    genai_client = genai.Client(vertexai=True, project=args.project, location=args.region)

    eligible_ids = governance.fetch_currently_eligible_ids(bq_client, args.project)
    cases = load_benchmark()

    results = [run_case(genai_client, bq_client, args.project, eligible_ids, case) for case in cases]
    summarize(results)
    return 0


if __name__ == "__main__":
    sys.exit(main())
