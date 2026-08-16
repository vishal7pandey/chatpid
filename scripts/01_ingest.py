"""End-to-end ingestion: DEXPI XML -> pyDEXPI -> graph abstraction(s) -> Neo4j.

Usage:
    uv run python scripts/01_ingest.py
    uv run python scripts/01_ingest.py --file OTHER.xml --levels conceptual,process
"""

from __future__ import annotations

import argparse
from pathlib import Path

from chatpid.ingest import build_graph_abstractions, get_driver, load_dexpi_model, load_graph

DATA_DIR = Path(__file__).resolve().parent.parent / "data" / "raw"
VALID_LEVELS = ("complete", "process", "conceptual")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--file", default="C01V04-VER.EX01.xml", help="XML filename in data/raw/")
    parser.add_argument(
        "--levels",
        default="conceptual",
        help="Comma-separated subset of complete,process,conceptual (default: conceptual, matching the paper's main config)",
    )
    args = parser.parse_args()

    levels = [level.strip() for level in args.levels.split(",")]
    for level in levels:
        if level not in VALID_LEVELS:
            raise SystemExit(f"Unknown level {level!r}; choose from {VALID_LEVELS}")

    print(f"Loading {args.file} ...")
    model = load_dexpi_model(DATA_DIR, args.file)

    print("Building graph abstractions ...")
    graphs = build_graph_abstractions(model)

    driver = get_driver()
    try:
        for level in levels:
            graph = getattr(graphs, level)
            print(
                f"Pushing '{level}' graph ({graph.number_of_nodes()} nodes, "
                f"{graph.number_of_edges()} edges) to Neo4j ..."
            )
            load_graph(driver, graph, level)
    finally:
        driver.close()

    print("Done. Try: uv run python scripts/ask.py \"Describe the process flow.\"")


if __name__ == "__main__":
    main()
