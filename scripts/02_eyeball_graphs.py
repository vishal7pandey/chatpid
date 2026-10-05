"""Eyeball the DEXPI reference P&ID's three graph levels by hand.

Loads C01V04-VER.EX01.xml, builds complete/process/conceptual graphs, and
prints node/edge counts, sample node attributes, and sample edges so we can
sanity-check pyDEXPI's attribute mapping before loading into Neo4j.
"""

from __future__ import annotations

from pathlib import Path

from chatpid.ingest import build_graph_abstractions, load_dexpi_model

DATA_DIR = Path(__file__).resolve().parent.parent / "data" / "raw"
FILENAME = "C01V04-VER.EX01.xml"


def main() -> None:
    print(f"=== Loading {FILENAME} ===")
    model = load_dexpi_model(DATA_DIR, FILENAME)
    print(f"Loaded pyDEXPI model: {type(model).__name__}")

    print("\n=== Building graph abstractions ===")
    graphs = build_graph_abstractions(model)

    for level_name in ("complete", "process", "conceptual"):
        graph = getattr(graphs, level_name)
        print(f"\n{'='*60}")
        print(f"LEVEL: {level_name}")
        print(f"  Nodes: {graph.number_of_nodes()}")
        print(f"  Edges: {graph.number_of_edges()}")
        print(f"  Graph type: {type(graph).__name__}")

        # --- Node attribute keys (what properties does pyDEXPI give us?) ---
        all_node_keys: set[str] = set()
        for _, data in graph.nodes(data=True):
            all_node_keys.update(data.keys())
        print(f"  Node attribute keys ({len(all_node_keys)}): {sorted(all_node_keys)}")

        # --- Sample 5 nodes with their full data ---
        print(f"\n  Sample nodes (first 5):")
        for i, (node_id, data) in enumerate(graph.nodes(data=True)):
            if i >= 5:
                break
            # Truncate long values for readability
            short_data = {}
            for k, v in data.items():
                v_str = str(v)
                if len(v_str) > 120:
                    v_str = v_str[:120] + "..."
                short_data[k] = v_str
            print(f"    [{i}] id={node_id}")
            for k, v in short_data.items():
                print(f"        {k}: {v}")

        # --- Edge attribute keys ---
        all_edge_keys: set[str] = set()
        for _, _, data in graph.edges(data=True):
            all_edge_keys.update(data.keys())
        print(f"\n  Edge attribute keys ({len(all_edge_keys)}): {sorted(all_edge_keys)}")

        # --- Sample 5 edges ---
        print(f"\n  Sample edges (first 5):")
        for i, (src, tgt, data) in enumerate(graph.edges(data=True)):
            if i >= 5:
                break
            short_data = {}
            for k, v in data.items():
                v_str = str(v)
                if len(v_str) > 100:
                    v_str = v_str[:100] + "..."
                short_data[k] = v_str
            print(f"    [{i}] {src} -> {tgt}")
            for k, v in short_data.items():
                print(f"        {k}: {v}")

        # --- Node label/type distribution ---
        type_counts: dict[str, int] = {}
        for _, data in graph.nodes(data=True):
            labels = data.get("labels") or [data.get("type", "Unknown")]
            for label in labels:
                type_counts[str(label)] = type_counts.get(str(label), 0) + 1
        print(f"\n  Node type distribution:")
        for t, c in sorted(type_counts.items(), key=lambda x: -x[1]):
            print(f"    {t}: {c}")

    # --- Check for 'tag' attribute (ContextRAG relies on it) ---
    print(f"\n{'='*60}")
    print("TAG ATTRIBUTE CHECK (ContextRAG uses node.tag):")
    for level_name in ("complete", "process", "conceptual"):
        graph = getattr(graphs, level_name)
        has_tag = sum(1 for _, d in graph.nodes(data=True) if d.get("tag"))
        total = graph.number_of_nodes()
        print(f"  {level_name}: {has_tag}/{total} nodes have 'tag' attribute")

    # --- Check for 'labels' attribute (Neo4j loader uses it) ---
    print("\nLABELS ATTRIBUTE CHECK (Neo4j loader uses node.labels):")
    for level_name in ("complete", "process", "conceptual"):
        graph = getattr(graphs, level_name)
        has_labels = sum(1 for _, d in graph.nodes(data=True) if d.get("labels"))
        total = graph.number_of_nodes()
        print(f"  {level_name}: {has_labels}/{total} nodes have 'labels' attribute")


if __name__ == "__main__":
    main()
