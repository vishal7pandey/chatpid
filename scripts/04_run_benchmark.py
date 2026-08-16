"""Run the paper's 19-question benchmark against the ChatP&ID agent.

Usage:
    uv run python scripts/04_run_benchmark.py
    uv run python scripts/04_run_benchmark.py --level conceptual --limit 5

SCRUM-358: hand-run the 19-question benchmark
SCRUM-359: track $ and tokens per question from the first run
"""

from __future__ import annotations

import argparse
import json
import time
from pathlib import Path

from chatpid.eval import print_summary, run_benchmark

RESULTS_DIR = Path(__file__).resolve().parent.parent / "data"


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--level",
        default="conceptual",
        choices=["complete", "process", "conceptual"],
        help="Graph abstraction level to test (default: conceptual, paper's best)",
    )
    parser.add_argument(
        "--limit",
        type=int,
        default=None,
        help="Run only the first N questions (default: all 19)",
    )
    parser.add_argument(
        "--output",
        default=None,
        help="Output file (default: data/benchmark_results_{level}_{timestamp}.json)",
    )
    args = parser.parse_args()

    print(f"Running benchmark: level={args.level}, model from .env")
    results = run_benchmark(level=args.level, limit=args.limit)
    print_summary(results, args.level)

    if args.output:
        outpath = Path(args.output)
    else:
        RESULTS_DIR.mkdir(exist_ok=True)
        timestamp = time.strftime("%Y%m%d_%H%M%S")
        outpath = RESULTS_DIR / f"benchmark_results_{args.level}_{timestamp}.json"

    outpath.write_text(json.dumps(results, indent=2, ensure_ascii=False), encoding="utf-8")
    print(f"\n  Results saved to: {outpath}")


if __name__ == "__main__":
    main()
