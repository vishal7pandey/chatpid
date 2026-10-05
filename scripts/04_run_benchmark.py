"""Run the paper's 19-question benchmark against the ChatP&ID agent.

Usage:
    uv run python scripts/04_run_benchmark.py
    uv run python scripts/04_run_benchmark.py --level conceptual --limit 5
    uv run python scripts/04_run_benchmark.py --resume data/benchmark_results_<level>_<timestamp>.json

Hand-run the 19-question benchmark and track $ and tokens per question from the first run.
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
    parser.add_argument(
        "--resume",
        default=None,
        help="Path to a previous results JSON file. Completed questions are skipped, "
        "new results are merged with the old ones.",
    )
    parser.add_argument(
        "--delay",
        type=float,
        default=5.0,
        help="Seconds to wait between questions (rate-limit protection, default: 5)",
    )
    args = parser.parse_args()

    # Load previous results if resuming
    previous_results = []
    skip_ids = []
    if args.resume:
        resume_path = Path(args.resume)
        if not resume_path.exists():
            print(f"ERROR: resume file not found: {resume_path}")
            return
        previous_results = json.loads(resume_path.read_text(encoding="utf-8"))
        skip_ids = [
            r["id"]
            for r in previous_results
            if not r.get("agent_answer", "").startswith("ERROR")
        ]
        print(
            f"Resuming from {resume_path.name}: {len(skip_ids)} questions already completed, "
            f"{19 - len(skip_ids)} remaining"
        )

    print(f"Running benchmark: level={args.level}, delay={args.delay}s")
    new_results = run_benchmark(
        level=args.level, limit=args.limit, delay=args.delay, skip_ids=skip_ids
    )

    # Merge: previous results (non-error) + new results
    all_results = previous_results + new_results
    # Sort by id and dedupe (new results take precedence)
    seen = {}
    for r in all_results:
        seen[r["id"]] = r
    merged = sorted(seen.values(), key=lambda r: r["id"])

    print_summary(merged, args.level)

    if args.output:
        outpath = Path(args.output)
    else:
        RESULTS_DIR.mkdir(exist_ok=True)
        timestamp = time.strftime("%Y%m%d_%H%M%S")
        outpath = RESULTS_DIR / f"benchmark_results_{args.level}_{timestamp}.json"

    outpath.write_text(
        json.dumps(merged, indent=2, ensure_ascii=False), encoding="utf-8"
    )
    print(f"\n  Results saved to: {outpath}")


if __name__ == "__main__":
    main()
