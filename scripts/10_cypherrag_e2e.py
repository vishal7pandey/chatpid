"""CypherRAG end-to-end test — LLM generates Cypher from natural language.

Tests the full CypherRAG pipeline (question → LLM generates Cypher → execute → LLM answers)
on the 19 benchmark questions. This is the first time we test LLM-generated Cypher
(not hand-written).

Usage:
    uv run python scripts/10_cypherrag_e2e.py
    uv run python scripts/10_cypherrag_e2e.py --limit 5  # quick test
"""

from __future__ import annotations

import argparse
import json
import time
from pathlib import Path

from chatpid.benchmark import BENCHMARK_QUESTIONS
from chatpid.cypher_rag import cypher_rag
from chatpid.ingest import get_driver

RESULTS_DIR = Path(__file__).resolve().parent.parent / "data"


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--limit", type=int, default=None)
    parser.add_argument("--delay", type=float, default=1.0)
    args = parser.parse_args()

    driver = get_driver()
    questions = BENCHMARK_QUESTIONS[: args.limit] if args.limit else BENCHMARK_QUESTIONS
    results = []

    print(f"CypherRAG end-to-end: {len(questions)} questions")
    print("=" * 60)

    for q in questions:
        print(f"\n[{q['id']}/19] ({q['category']}) {q['question'][:80]}...")

        try:
            start = time.time()
            result = cypher_rag(driver, q["question"], level="conceptual")
            elapsed = time.time() - start

            entry = {
                "id": q["id"],
                "category": q["category"],
                "question": q["question"],
                "reference_answer": q["reference_answer"],
                "agent_answer": result["answer"],
                "cypher": result["cypher"],
                "results_count": len(result["results"]),
                "latency_seconds": round(elapsed, 2),
            }
            results.append(entry)
            print(f"  Cypher: {result['cypher'][:120]}...")
            print(f"  Results: {len(result['results'])} rows")
            print(f"  Answer: {result['answer'][:120]}...")
            print(f"  Time: {elapsed:.1f}s")

        except Exception as exc:
            entry = {
                "id": q["id"],
                "category": q["category"],
                "question": q["question"],
                "reference_answer": q["reference_answer"],
                "agent_answer": f"ERROR: {exc!s:.200}",
                "cypher": "",
                "results_count": 0,
                "latency_seconds": 0.0,
                "error": str(exc),
            }
            results.append(entry)
            print(f"  ERROR: {exc!s:.200}")

        if args.delay > 0:
            time.sleep(args.delay)

    # Summary
    print(f"\n{'=' * 60}")
    print(f"CYPHERRAG E2E SUMMARY ({len(results)} questions)")
    ok = sum(1 for r in results if not r["agent_answer"].startswith("ERROR"))
    print(f"  Success: {ok}/{len(results)}")
    avg_latency = sum(r["latency_seconds"] for r in results) / len(results)
    print(f"  Avg latency: {avg_latency:.1f}s")

    # Save
    RESULTS_DIR.mkdir(exist_ok=True)
    timestamp = time.strftime("%Y%m%d_%H%M%S")
    outpath = RESULTS_DIR / f"cypherrag_e2e_{timestamp}.json"
    outpath.write_text(
        json.dumps(results, indent=2, ensure_ascii=False), encoding="utf-8"
    )
    print(f"  Results saved to: {outpath}")

    driver.close()


if __name__ == "__main__":
    main()
