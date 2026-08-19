"""SCRUM-474: Ingest persisted synthetic P&ID from GraphML into Neo4j.

Loads the synthetic P&ID graphs (previously persisted by scripts/21_generate_synthetic_pid.py --persist)
from data/synthetic/*.graphml and ingests them into Neo4j.

This allows the synthetic P&ID to survive Neo4j restarts without re-running
the generation step (which is non-deterministic without the same seed).

Usage:
    uv run python scripts/23_ingest_synthetic.py
    uv run python scripts/23_ingest_synthetic.py --dir data/synthetic --clear
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path

import networkx as nx


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--dir", default="data/synthetic",
                        help="Directory containing persisted GraphML files (default: data/synthetic)")
    parser.add_argument("--clear", action="store_true",
                        help="Clear existing Neo4j data before ingesting")
    parser.add_argument("--levels", default="complete,process,conceptual",
                        help="Comma-separated subset of complete,process,conceptual")
    args = parser.parse_args()

    persist_dir = Path(args.dir)
    if not persist_dir.exists():
        print(f"Error: {persist_dir} does not exist.")
        print("Run scripts/21_generate_synthetic_pid.py --persist first.")
        return

    # Load metadata
    meta_path = persist_dir / "metadata.json"
    if meta_path.exists():
        with open(meta_path) as f:
            meta = json.load(f)
        print(f"Synthetic P&ID metadata:")
        print(f"  Seed: {meta.get('seed')}")
        print(f"  Node counts: {meta.get('node_counts')}")
        print(f"  Edge counts: {meta.get('edge_counts')}")
        print(f"  Equipment types: {len(meta.get('equipment_types', {}))} unique")
    else:
        print(f"Warning: no metadata.json found in {persist_dir}")

    # Load graphs from GraphML
    levels = args.levels.split(",")
    graphs = {}
    for level in levels:
        graphml_path = persist_dir / f"{level}.graphml"
        if not graphml_path.exists():
            print(f"Warning: {graphml_path} not found, skipping {level}")
            continue
        g = nx.read_graphml(graphml_path)
        # Convert to MultiDiGraph (GraphML saves as DiGraph)
        g = nx.MultiDiGraph(g)
        graphs[level] = g
        print(f"Loaded {level}: {g.number_of_nodes()} nodes, {g.number_of_edges()} edges")

    if not graphs:
        print("No graphs loaded. Nothing to ingest.")
        return

    # Ingest into Neo4j
    from chatpid.ingest import get_driver, load_graph

    print("\nIngesting into Neo4j...")
    driver = get_driver()
    try:
        if args.clear:
            print("Clearing existing synthetic data...")
            with driver.session() as session:
                session.run("MATCH (n {document_id: 'synthetic'}) DETACH DELETE n")

        for level, g in graphs.items():
            print(f"  Loading {level} ({g.number_of_nodes()} nodes)...")
            load_graph(driver, g, level, document_id="synthetic")
        print("Ingestion complete!")
    finally:
        driver.close()


if __name__ == "__main__":
    main()
