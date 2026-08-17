"""Score model benchmark results (SCRUM-373).

Takes the dict-of-lists format from 17_model_benchmark.py and scores each
combo with the LLM-as-judge + semantic similarity.

Usage:
    uv run python scripts/18_score_model_benchmark.py data/model_benchmark_YYYYMMDD_HHMMSS.json
"""

from __future__ import annotations

import argparse
import json
import sys
import time
from pathlib import Path

from chatpid.scoring import score_result


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("filepath", help="Path to model_benchmark JSON")
    parser.add_argument("--delay", type=float, default=1.0)
    args = parser.parse_args()

    data = json.loads(Path(args.filepath).read_text(encoding="utf-8"))
    all_scored = {}

    for combo_key, results in data.items():
        print(f"\n{'='*60}")
        print(f"Scoring: {combo_key} ({len(results)} questions)")
        print(f"{'='*60}")

        scored = []
        for i, entry in enumerate(results):
            print(f"  [{i+1}/{len(results)}] Q{entry.get('id', '?')}: ", end="", flush=True)
            try:
                scored_entry = score_result(entry)
                verdict = scored_entry["llm_judge"].get("verdict", "?")
                sim = scored_entry.get("semantic_similarity", 0)
                print(f"{verdict} (sim={sim:.3f})")
            except Exception as e:
                print(f"ERROR: {e!s:.80}")
                scored_entry = {**entry, "llm_judge": {"verdict": "error", "score": 0}, "semantic_similarity": 0}
            scored.append(scored_entry)
            if args.delay > 0:
                time.sleep(args.delay)

        all_scored[combo_key] = scored

    # Print summary grid
    print(f"\n{'='*90}")
    print("SCORED MODEL x TOOL GRID")
    print(f"{'='*90}")
    print(f"{'Model_Tool':<30} {'Correct':>8} {'Partial':>8} {'Incorrect':>10} {'Error':>6} {'Avg Sim':>8}")
    print("-" * 90)

    for combo_key, scored in all_scored.items():
        n = len(scored)
        correct = sum(1 for s in scored if s.get("llm_judge", {}).get("verdict") == "correct")
        partial = sum(1 for s in scored if s.get("llm_judge", {}).get("verdict") == "partial")
        incorrect = sum(1 for s in scored if s.get("llm_judge", {}).get("verdict") == "incorrect")
        error = sum(1 for s in scored if s.get("llm_judge", {}).get("verdict") == "error")
        avg_sim = sum(s.get("semantic_similarity", 0) for s in scored) / n if n else 0
        print(f"{combo_key:<30} {correct:>6}/{n} {partial:>6}/{n} {incorrect:>8}/{n} {error:>4}/{n} {avg_sim:>8.3f}")

    # Save
    base = args.filepath.rsplit(".", 1)[0]
    out_path = f"{base}_scored.json"
    Path(out_path).write_text(json.dumps(all_scored, indent=2, ensure_ascii=False), encoding="utf-8")
    print(f"\nSaved to: {out_path}")


if __name__ == "__main__":
    main()
