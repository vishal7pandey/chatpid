"""14_score_benchmark.py — Score benchmark results with LLM-as-judge + semantic similarity.

Usage:
  uv run python scripts/14_score_benchmark.py data/direct_benchmark_conceptual_20260816_200408.json
  uv run python scripts/14_score_benchmark.py --latest

Mirrors the paper's Section 4.3 methodology.
"""

import argparse
import glob
import os
import sys
import time

from chatpid.scoring import (
    load_results,
    print_score_summary,
    save_scored_results,
    score_results,
)


def find_latest_results() -> str | None:
    """Find the most recent benchmark results file."""
    files = sorted(glob.glob("data/*benchmark*.json"))
    # Prefer files with 19 questions (complete runs)
    complete = []
    for f in files:
        try:
            import json
            data = json.load(open(f))
            if isinstance(data, list) and len(data) == 19:
                complete.append(f)
        except Exception:
            pass
    if complete:
        return complete[-1]
    return files[-1] if files else None


def main():
    parser = argparse.ArgumentParser(description="Score benchmark results")
    parser.add_argument("filepath", nargs="?", help="Path to benchmark results JSON")
    parser.add_argument("--latest", action="store_true", help="Use latest 19-question results")
    parser.add_argument("--delay", type=float, default=1.0, help="Delay between questions (rate limit)")
    args = parser.parse_args()

    filepath = args.filepath
    if args.latest or not filepath:
        filepath = find_latest_results()
        if not filepath:
            print("No benchmark results found in data/")
            sys.exit(1)
        print(f"Using latest results: {filepath}")

    if not os.path.exists(filepath):
        print(f"File not found: {filepath}")
        sys.exit(1)

    print(f"Loading results from {filepath}...")
    results = load_results(filepath)
    print(f"Loaded {len(results)} results")

    print(f"\nScoring {len(results)} questions...")
    scored = []
    for i, entry in enumerate(results):
        print(f"  [{i+1}/{len(results)}] Q{entry.get('id', '?')}: ", end="", flush=True)
        from chatpid.scoring import score_result
        scored_entry = score_result(entry)
        scored.append(scored_entry)
        verdict = scored_entry["llm_judge"].get("verdict", "?")
        sim = scored_entry.get("semantic_similarity", 0)
        print(f"{verdict} (sim={sim:.3f})")
        if args.delay > 0:
            time.sleep(args.delay)

    print_score_summary(scored)

    # Save scored results
    base, ext = os.path.splitext(filepath)
    out_path = f"{base}_scored{ext}"
    save_scored_results(scored, out_path)


if __name__ == "__main__":
    main()
