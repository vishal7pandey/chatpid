"""End-to-end ingestion: DEXPI XML -> pyDEXPI -> graph abstraction(s) -> Neo4j.

Usage:
    uv run python scripts/01_ingest.py
    uv run python scripts/01_ingest.py --file OTHER.xml --levels conceptual,process
    uv run python scripts/01_ingest.py --document-id C01V04
"""

from __future__ import annotations

import argparse
from pathlib import Path

from chatpid.ingest import build_graph_abstractions, get_driver, load_dexpi_model, load_graph

DATA_DIR = Path(__file__).resolve().parent.parent / "data" / "raw"
VALID_LEVELS = ("complete", "process", "conceptual")


def _derive_document_id(filename: str) -> str:
    """Derive a document_id from the DEXPI filename.

    e.g. 'C01V04-VER.EX01.xml' -> 'C01V04'
    """
    stem = Path(filename).stem  # 'C01V04-VER.EX01'
    # Take the first hyphen-separated segment (the case ID + version)
    return stem.split("-")[0]


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--file", default="C01V04-VER.EX01.xml", help="XML filename in data/raw/")
    parser.add_argument(
        "--levels",
        default="conceptual",
        help="Comma-separated subset of complete,process,conceptual (default: conceptual, matching the paper's main config)",
    )
    parser.add_argument(
        "--document-id",
        default=None,
        help="Document ID for per-document scoping (default: derived from filename, e.g. C01V04)",
    )
    args = parser.parse_args()

    levels = [level.strip() for level in args.levels.split(",")]
    for level in levels:
        if level not in VALID_LEVELS:
            raise SystemExit(f"Unknown level {level!r}; choose from {VALID_LEVELS}")

    document_id = args.document_id or _derive_document_id(args.file)

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
                f"{graph.number_of_edges()} edges) to Neo4j as document_id={document_id} ..."
            )
            load_graph(driver, graph, level, document_id=document_id)
    finally:
        driver.close()

    print(f"Done. document_id={document_id}")
    print(f'Try: uv run python scripts/ask.py "Describe the process flow."')


if __name__ == "__main__":
    main()
