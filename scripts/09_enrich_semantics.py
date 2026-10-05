"""Run semantic enrichment on all nodes at a given level.

Generates global + local semantic descriptions for every node using the LLM,
then writes them back to Neo4j as `global_semantic` and `local_semantic` properties.

Usage:
    uv run python scripts/09_enrich_semantics.py --level conceptual
    uv run python scripts/09_enrich_semantics.py --level process
    uv run python scripts/09_enrich_semantics.py --level complete
"""

from __future__ import annotations

import argparse
import json
import time
from pathlib import Path

from chatpid.ingest import get_driver
from chatpid.semantic_enrichment import enrich_all_nodes

RESULTS_DIR = Path(__file__).resolve().parent.parent / "data"


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--level", default="conceptual", choices=["complete", "process", "conceptual"]
    )
    parser.add_argument(
        "--delay", type=float, default=0.5, help="Delay between LLM calls (seconds)"
    )
    args = parser.parse_args()

    driver = get_driver()
    print(f"Semantic enrichment: level={args.level}, delay={args.delay}s")
    print("=" * 60)

    start = time.time()
    results = enrich_all_nodes(driver, level=args.level, delay=args.delay, verbose=True)
    elapsed = time.time() - start

    print(f"\nTotal time: {elapsed:.1f}s")

    # Save results
    RESULTS_DIR.mkdir(exist_ok=True)
    timestamp = time.strftime("%Y%m%d_%H%M%S")
    outpath = RESULTS_DIR / f"semantic_enrichment_{args.level}_{timestamp}.json"
    data = [
        {
            "element_id": r.element_id,
            "tag": r.tag,
            "global_semantic": r.global_semantic,
            "local_semantic": r.local_semantic,
        }
        for r in results
    ]
    outpath.write_text(json.dumps(data, indent=2, ensure_ascii=False), encoding="utf-8")
    print(f"Results saved to: {outpath}")

    # Print sample
    print("\n--- Sample (first 3 nodes) ---")
    for r in results[:3]:
        print(f"\n[{r.tag}]")
        print(f"  Global: {r.global_semantic[:200]}")
        print(f"  Local:  {r.local_semantic[:200]}")

    driver.close()


if __name__ == "__main__":
    main()
