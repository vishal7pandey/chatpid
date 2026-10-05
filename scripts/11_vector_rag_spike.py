"""Embed node semantics, create vector indexes, and eyeball VectorRAG top-k.

1. Embeds global_semantic and local_semantic for all nodes at a given level
2. Creates Neo4j vector indexes
3. Runs sample queries to eyeball the top-k results

Usage:
    uv run python scripts/11_vector_rag_spike.py --level conceptual
"""

from __future__ import annotations

import argparse
import time

from chatpid.ingest import get_driver
from chatpid.vector_rag import embed_and_store, ensure_vector_indexes, vector_rag_text

# Sample queries to test VectorRAG — covering all 4 benchmark categories
TEST_QUERIES = [
    # graph_query_single
    "What is the cylinder length of tank T4750?",
    "What is the design pressure of pump P4711?",
    # graph_query_multi
    "List all valves in the P&ID",
    "List all pipe fittings",
    # path_exploration
    "Trace the flow path from tank T4750 to pump P4712",
    "How to isolate tank T4750 from upstream equipment",
    # knowledge_inference
    "How to control process stream temperature",
    "Process safety recommendations",
    # graph_summarization
    "Describe the process flow from inlet to outlet",
]


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--level", default="conceptual", choices=["complete", "process", "conceptual"]
    )
    parser.add_argument("--top-k", type=int, default=5)
    args = parser.parse_args()

    driver = get_driver()

    print("=" * 60)
    print(f"VectorRAG spike: level={args.level}")
    print("=" * 60)

    # Step 1: Embed all nodes
    print("\n--- Step 1: Embedding node semantics ---")
    start = time.time()
    count = embed_and_store(driver, level=args.level)
    elapsed = time.time() - start
    print(f"Embedded {count} nodes in {elapsed:.1f}s")

    # Step 2: Create vector indexes
    print("\n--- Step 2: Creating vector indexes ---")
    ensure_vector_indexes(driver, dimensions=384)

    # Step 3: Test queries with global index
    print("\n" + "=" * 60)
    print(f"--- Step 3: VectorRAG top-{args.top_k} results (global index) ---")
    print("=" * 60)

    for query in TEST_QUERIES:
        print(f"\nQuery: {query}")
        text = vector_rag_text(
            driver,
            query,
            index="global_semantic_index",
            top_k=args.top_k,
            level=args.level,
        )
        print(text)

    # Step 4: Test with local index
    print("\n" + "=" * 60)
    print(f"--- Step 4: VectorRAG top-{args.top_k} results (local index) ---")
    print("=" * 60)

    for query in TEST_QUERIES[:4]:  # fewer queries for local index
        print(f"\nQuery: {query}")
        text = vector_rag_text(
            driver,
            query,
            index="local_semantic_index",
            top_k=args.top_k,
            level=args.level,
        )
        print(text)

    driver.close()
    print("\nDone.")


if __name__ == "__main__":
    main()
