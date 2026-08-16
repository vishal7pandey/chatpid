"""Compare ContextRAG accuracy/cost across all 3 graph abstraction levels.

SCRUM-360: The paper's headline claim is "conceptual graph wins on cost and
often accuracy." That was measured on exactly one small P&ID. This script runs
the same 19 questions against complete/process/conceptual levels and prints a
comparison table so we can check whether "always default to conceptual" holds
on our own diagram.

Usage:
    uv run python scripts/05_compare_levels.py
    uv run python scripts/05_compare_levels.py --limit 5  # quick test

Prerequisites: Neo4j running with all 3 levels loaded, GOOGLE_API_KEY set.
"""

from __future__ import annotations

import argparse
import json
import time
from pathlib import Path

from chatpid.eval import print_summary, run_benchmark

LEVELS = ("complete", "process", "conceptual")
RESULTS_DIR = Path(__file__).resolve().parent.parent / "data"


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--limit", type=int, default=None, help="Run only first N questions per level")
    args = parser.parse_args()

    all_results = {}
    for level in LEVELS:
        print(f"\n{'='*60}")
        print(f"Running benchmark: level={level}")
        print(f"{'='*60}")
        results = run_benchmark(level=level, limit=args.limit)
        all_results[level] = results
        print_summary(results, level)

    # Comparison table
    print(f"\n{'='*60}")
    print("LEVEL COMPARISON TABLE")
    print(f"{'='*60}")
    print(f"{'Level':<15} {'Total Cost':>12} {'Avg Cost/Q':>12} {'Avg Tokens/Q':>14}")
    print("-" * 55)

    for level in LEVELS:
        results = all_results[level]
        total_cost = sum(r["cost_usd"] for r in results)
        total_tokens = sum(r["tokens"]["total_tokens"] for r in results)
        n = len(results)
        print(
            f"{level:<15} "
            f"${total_cost:>10.4f} "
            f"${total_cost / n:>10.6f} "
            f"{total_tokens / n:>13,.0f}"
        )

    RESULTS_DIR.mkdir(exist_ok=True)
    timestamp = time.strftime("%Y%m%d_%H%M%S")
    outpath = RESULTS_DIR / f"level_comparison_{timestamp}.json"
    outpath.write_text(
        json.dumps(all_results, indent=2, ensure_ascii=False), encoding="utf-8"
    )
    print(f"\nResults saved to: {outpath}")


if __name__ == "__main__":
    main()
