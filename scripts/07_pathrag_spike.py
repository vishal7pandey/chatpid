"""PathRAG spike — hand-trace paths in the graph.

Tests PathRAG on the paper's canonical path-exploration questions:
  - "Trace the flow path from tank T4750 to pump P4712"
  - "How to control process stream temperature"
  - "Isolate tank T4750 from all upstream equipment"

Also tests CypherRAG's schema introspection.

Usage:
    uv run python scripts/07_pathrag_spike.py
"""

from __future__ import annotations

from chatpid.cypher_rag import get_graph_schema
from chatpid.ingest import get_driver
from chatpid.path_rag import find_starting_nodes, get_neighbors, path_rag_text


def main() -> None:
    driver = get_driver()

    print("=" * 60)
    print("PATHRAG SPIKE — hand-tracing paths through the P&ID graph")
    print("=" * 60)

    # --- Test 1: Schema introspection (CypherRAG prerequisite) ---
    print("\n--- CypherRAG: Graph Schema (conceptual level) ---")
    schema = get_graph_schema(driver, level="conceptual")
    print(schema)

    # --- Test 2: Find starting nodes for path queries ---
    print("\n--- PathRAG: Starting node selection ---")
    test_queries = [
        "Trace the flow path from tank T4750 to pump P4712",
        "How to control process stream temperature",
        "Isolate tank T4750 from all upstream equipment",
        "What is the flow path from pump P4711 to tank T4750",
    ]

    for q in test_queries:
        print(f"\nQuery: {q}")
        starts = find_starting_nodes(driver, q, level="conceptual", max_breadth=2)
        for s in starts:
            print(f"  -> [{s['tag']}] ({s.get('label', '')}) score={s['_score']:.3f}")

    # --- Test 3: Full path tracing ---
    print("\n" + "=" * 60)
    print("--- PathRAG: Full path traces ---")
    print("=" * 60)

    path_queries = [
        ("Trace the flow path from tank T4750 to pump P4712", "conceptual"),
        ("What is the flow path from pump P4711 to tank T4750", "conceptual"),
        ("How to control process stream temperature", "conceptual"),
        ("Isolate tank T4750 from all upstream equipment", "conceptual"),
    ]

    for query, level in path_queries:
        print(f"\n{'=' * 60}")
        print(f"Query: {query}")
        print(f"Level: {level}, max_depth=5, max_breadth=2")
        print(f"{'=' * 60}")
        text = path_rag_text(driver, query, level=level, max_depth=5, max_breadth=2)
        print(text)

    # --- Test 4: Neighbor inspection for key nodes ---
    print("\n" + "=" * 60)
    print("--- Neighbors of key nodes ---")
    print("=" * 60)

    for tag in ["T4750", "P4711", "P4712", "H1007", "H1008"]:
        print(f"\n[{tag}] neighbors:")
        neighbors = get_neighbors(driver, tag, level="conceptual")
        for n in neighbors:
            arrow = "-->" if n["direction"] == "out" else "<--"
            print(
                f"  {tag} {arrow} [{n['tag']}] ({n.get('label', '')}) via {n['rel_type']}"
            )

    driver.close()
    print("\nDone.")


if __name__ == "__main__":
    main()
