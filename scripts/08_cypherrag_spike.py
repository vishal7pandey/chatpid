"""SCRUM-364: CypherRAG spike — test Cypher execution on 3 canonical patterns.

Tests the three most common Cypher query patterns for P&ID questions:
  1. Single-node attribute lookup (graph_query_single)
  2. Multi-node listing by label (graph_query_multi)
  3. Path traversal between two nodes (path_exploration)

Also tests the schema introspection that CypherRAG uses to prompt the LLM.

Usage:
    uv run python scripts/08_cypherrag_spike.py
"""

from __future__ import annotations

from chatpid.cypher_rag import execute_cypher, get_graph_schema
from chatpid.ingest import get_driver


def main() -> None:
    driver = get_driver()

    print("=" * 60)
    print("CYPHERRAG SPIKE — Cypher execution on canonical patterns")
    print("=" * 60)

    # --- Schema ---
    print("\n--- Graph Schema (conceptual level, first 30 lines) ---")
    schema = get_graph_schema(driver, level="conceptual")
    for line in schema.split("\n")[:30]:
        print(line)

    # --- Pattern 1: Single-node attribute lookup ---
    print("\n" + "=" * 60)
    print("--- Pattern 1: Single-node attribute lookup ---")
    print("=" * 60)

    queries_p1 = [
        # Q1: cylinder length of tank T4750
        """
        MATCH (n {tag: 'T4750', level: 'conceptual'})
        RETURN n.tag AS tag, n.cylinderLength AS cylinderLength
        """,
        # Q2: design heat transfer area of H1007
        """
        MATCH (n {tag: 'H1007', level: 'conceptual'})
        RETURN n.tag AS tag, n.designHeatTransferArea AS designHeatTransferArea
        """,
        # Q3: design pressure head of pump P4711
        """
        MATCH (n {tag: 'P4711', level: 'conceptual'})
        RETURN n.tag AS tag, n.designPressureHead AS designPressureHead
        """,
        # Q7: set pressure of safety valve SV 104.01
        """
        MATCH (n {tag: 'SV 104.01', level: 'conceptual'})
        RETURN n.tag AS tag, n.setPressureHigh AS setPressure
        """,
    ]

    for i, cypher in enumerate(queries_p1, 1):
        print(f"\nQuery {i}: {cypher.strip().split(chr(10))[1].strip()}")
        try:
            results = execute_cypher(driver, cypher)
            for row in results:
                print(f"  Result: {row}")
        except Exception as exc:
            print(f"  ERROR: {exc}")

    # --- Pattern 2: Multi-node listing by label ---
    print("\n" + "=" * 60)
    print("--- Pattern 2: Multi-node listing by label ---")
    print("=" * 60)

    # List all valves
    cypher_valves = """
    MATCH (n {level: 'conceptual'})
    WHERE n.label CONTAINS 'Valve'
    RETURN n.tag AS tag, n.label AS type, n.nominalDiameterRepresentation AS diameter,
           n.pipingClassCode AS pipingClass, n.fluidCode AS fluidCode
    ORDER BY n.tag
    """
    print("\nQuery: List all valves")
    try:
        results = execute_cypher(driver, cypher_valves)
        print(f"  Found {len(results)} valves:")
        for row in results:
            print(f"    {row}")
    except Exception as exc:
        print(f"  ERROR: {exc}")

    # List all pipe fittings
    cypher_fittings = """
    MATCH (n {level: 'conceptual'})
    WHERE n.label CONTAINS 'Pipe' OR n.label CONTAINS 'Blind' OR n.label CONTAINS 'Flange'
    RETURN n.tag AS tag, n.label AS type, n.nominalDiameterRepresentation AS diameter,
           n.pipingClassCode AS pipingClass, n.pipingComponentNumber AS componentNumber
    ORDER BY n.tag
    """
    print("\nQuery: List all pipe fittings")
    try:
        results = execute_cypher(driver, cypher_fittings)
        print(f"  Found {len(results)} fittings:")
        for row in results:
            print(f"    {row}")
    except Exception as exc:
        print(f"  ERROR: {exc}")

    # --- Pattern 3: Path traversal between two nodes ---
    print("\n" + "=" * 60)
    print("--- Pattern 3: Path traversal between two nodes ---")
    print("=" * 60)

    # Trace path from P4711 to T4750
    cypher_path = """
    MATCH path = shortestPath(
        (a {tag: 'P4711', level: 'conceptual'})
        -[:PIPE*..6]->
        (b {tag: 'T4750', level: 'conceptual'})
    )
    RETURN [node IN nodes(path) | node.tag] AS pathTags,
           [rel IN relationships(path) | type(rel)] AS relTypes
    """
    print("\nQuery: Shortest path P4711 -> T4750")
    try:
        results = execute_cypher(driver, cypher_path)
        for row in results:
            print(f"  Path: {' -> '.join(row['pathTags'])}")
            print(f"  Rels: {row['relTypes']}")
    except Exception as exc:
        print(f"  ERROR: {exc}")

    # Trace path from T4750 to P4712
    cypher_path2 = """
    MATCH path = shortestPath(
        (a {tag: 'T4750', level: 'conceptual'})
        -[:PIPE*..6]->
        (b {tag: 'P4712', level: 'conceptual'})
    )
    RETURN [node IN nodes(path) | node.tag] AS pathTags,
           [rel IN relationships(path) | type(rel)] AS relTypes
    """
    print("\nQuery: Shortest path T4750 -> P4712")
    try:
        results = execute_cypher(driver, cypher_path2)
        for row in results:
            print(f"  Path: {' -> '.join(row['pathTags'])}")
            print(f"  Rels: {row['relTypes']}")
    except Exception as exc:
        print(f"  ERROR: {exc}")

    # Find all valves connected to T4750 (isolation question)
    cypher_isolation = """
    MATCH (t {tag: 'T4750', level: 'conceptual'})-[:PIPE]-(v {level: 'conceptual'})
    WHERE v.label CONTAINS 'Valve'
    RETURN v.tag AS valveTag, v.label AS valveType, v.nominalDiameterRepresentation AS diameter
    """
    print("\nQuery: Valves directly connected to T4750")
    try:
        results = execute_cypher(driver, cypher_isolation)
        print(f"  Found {len(results)} valves:")
        for row in results:
            print(f"    {row}")
    except Exception as exc:
        print(f"  ERROR: {exc}")

    # --- Safety check: write operations should be rejected ---
    print("\n" + "=" * 60)
    print("--- Safety check: write operations rejected ---")
    print("=" * 60)
    try:
        execute_cypher(driver, "CREATE (n:Test {tag: 'evil'})")
        print("  FAIL: write operation was not rejected!")
    except ValueError as exc:
        print(f"  PASS: write operation rejected: {exc}")

    driver.close()
    print("\nDone.")


if __name__ == "__main__":
    main()
