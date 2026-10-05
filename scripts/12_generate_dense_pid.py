"""Generate a denser P&ID graph by duplicating the reference graph N times.

The DEXPI 1.2 test case files are incompatible with pyDEXPI (only supports 1.3),
and combine_dexpi_models deduplicates by proteusId. Instead, we duplicate the
NetworkX graph directly with unique tags (appending _copyN suffixes), then load
the larger graph to Neo4j. This directly tests the paper's scaling concern
(Section 6: "the scaling problem is real") — does ContextRAG/PathRAG/etc.
still work on a 3x or 5x larger graph?

Usage:
    uv run python scripts/12_generate_dense_pid.py --copies 3
    uv run python scripts/12_generate_dense_pid.py --copies 5 --level conceptual
"""

from __future__ import annotations

import argparse

import networkx as nx

from chatpid.ingest import build_graph_abstractions, get_driver, load_dexpi_model, load_graph

from pathlib import Path
DATA_DIR = Path(__file__).resolve().parent.parent / "data" / "raw"


def duplicate_graph(graph: nx.DiGraph, copies: int) -> nx.DiGraph:
    """Duplicate a graph N times with unique tags and node IDs.

    Each copy gets a suffix _c{N} on all tags and proteusId values.
    Edges within each copy are preserved; no cross-copy edges are added
    (each copy is an independent flowsheet).
    """
    combined = nx.DiGraph()

    for copy_idx in range(copies):
        suffix = f"_c{copy_idx}" if copy_idx > 0 else ""
        node_mapping = {}

        for node_id, attrs in graph.nodes(data=True):
            new_id = f"{node_id}{suffix}"
            new_attrs = dict(attrs)
            # Make tags unique
            if "tag" in new_attrs and new_attrs["tag"]:
                new_attrs["tag"] = f"{new_attrs['tag']}{suffix}"
            if "proteusId" in new_attrs and new_attrs["proteusId"]:
                new_attrs["proteusId"] = f"{new_attrs['proteusId']}{suffix}"
            combined.add_node(new_id, **new_attrs)
            node_mapping[node_id] = new_id

        for u, v, edge_attrs in graph.edges(data=True):
            new_u = node_mapping[u]
            new_v = node_mapping[v]
            combined.add_edge(new_u, new_v, **dict(edge_attrs))

    return combined


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--copies", type=int, default=3, help="Number of copies")
    parser.add_argument("--source", default="C01V04-VER.EX01.xml", help="Source XML file")
    parser.add_argument("--level", default="conceptual", help="Graph level to duplicate and load")
    args = parser.parse_args()

    print(f"Loading {args.source} ...")
    model = load_dexpi_model(DATA_DIR, args.source)

    print("Building graph abstractions ...")
    graphs = build_graph_abstractions(model)

    original = getattr(graphs, args.level)
    print(f"Original ({args.level}): {original.number_of_nodes()} nodes, {original.number_of_edges()} edges")

    print(f"Duplicating {args.copies}x ...")
    dense = duplicate_graph(original, args.copies)
    print(f"Dense ({args.level}): {dense.number_of_nodes()} nodes, {dense.number_of_edges()} edges")

    # Load to Neo4j with a special level name to avoid clobbering the original
    level_name = f"dense_{args.copies}x_{args.level}"
    document_id = f"dense_{args.copies}x"
    print(f"Loading to Neo4j as level='{level_name}', document_id='{document_id}' ...")
    driver = get_driver()
    try:
        load_graph(driver, dense, level_name, document_id=document_id)
    finally:
        driver.close()

    print(f"Done. The dense graph is in Neo4j as level='{level_name}'.")
    print(f"Test with: uv run python scripts/ask.py --level {level_name} \"Describe the process flow.\"")


if __name__ == "__main__":
    main()
