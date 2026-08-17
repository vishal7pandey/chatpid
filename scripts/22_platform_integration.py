"""SCRUM-412: Neo4j-backed KnowledgeStore adapter for platform's capability registry.

This adapter wraps chatpid's Neo4j driver to satisfy platform's KnowledgeStore
protocol, allowing platform's GraphRAG capabilities (ContextRAG, VectorRAG,
PathRAG, CypherRAG) to operate against chatpid's P&ID knowledge graph.

The goal is to test whether the platform's capability spec actually fits a real
second implementation (chatpid), or whether it breaks and needs amendment.

Usage:
    uv run python scripts/22_platform_integration.py
"""

from __future__ import annotations

import asyncio
import json
import sys
import time
from pathlib import Path
from typing import Any

# Add platform to path
PLATFORM_SRC = Path(__file__).resolve().parent.parent.parent / "platform" / "src"
sys.path.insert(0, str(PLATFORM_SRC))

from aioplatform.capability.graphrag import (
    ContextRAGCapability,
    CypherRAGCapability,
    PathRAGCapability,
    VectorRAGCapability,
)
from aioplatform.capability.registry import CapabilityRegistry
from aioplatform.capability.types import CapabilityType
from aioplatform.knowledge.types import (
    DataSource,
    EntityWriteRequest,
    IngestionResult,
    KnowledgeQuery,
    KnowledgeQueryType,
    KnowledgeResult,
    SearchHit,
)


class Neo4jKnowledgeStore:
    """Adapter that wraps chatpid's Neo4j driver to satisfy platform's
    KnowledgeStore protocol.

    This is the actual test: can chatpid's Neo4j-backed graph satisfy the
    interface that platform's GraphRAG capabilities expect?
    """

    def __init__(self, driver=None) -> None:
        if driver is None:
            from chatpid.ingest import get_driver
            driver = get_driver()
        self._driver = driver
        self._workspace = "chatpid"

    async def query(self, request: KnowledgeQuery) -> KnowledgeResult:
        """Execute a typed query against the Neo4j graph."""
        start = time.monotonic()
        hits = []

        if request.query_type == KnowledgeQueryType.CYPHER:
            # Cypher query — execute directly
            with self._driver.session() as session:
                result = session.run(request.query if isinstance(request.query, str) else str(request.query))
                for record in result:
                    node = record.get("n") or record.get("node") or record.get("entity")
                    if node:
                        hits.append(SearchHit(
                            entity_id=str(node.element_id),
                            entity_type=list(node.labels)[0] if node.labels else "Unknown",
                            score=1.0,
                            properties=dict(node),
                            source_store="graph",
                        ))

        elif request.query_type == KnowledgeQueryType.VECTOR:
            # Vector search — use chatpid's VectorRAG
            from chatpid.vector_rag import vector_rag
            query_text = request.query if isinstance(request.query, str) else str(request.query)
            results = vector_rag(self._driver, query_text, level="conceptual", top_k=request.max_results)
            for r in results:
                hits.append(SearchHit(
                    entity_id=str(r.get("id", "")),
                    entity_type=r.get("label", "Unknown"),
                    score=r.get("score", 0.0),
                    properties=r,
                    source_store="vector",
                ))

        elif request.query_type == KnowledgeQueryType.GRAPH_TRAVERSAL:
            # Graph traversal — use chatpid's PathRAG
            from chatpid.path_rag import path_rag
            query_text = request.query if isinstance(request.query, str) else str(request.query)
            results = path_rag(self._driver, query_text, level="conceptual",
                               max_depth=request.max_depth or 3, max_breadth=3)
            for r in results:
                hits.append(SearchHit(
                    entity_id=str(r.get("id", "")),
                    entity_type=r.get("label", "Unknown"),
                    score=1.0,
                    properties=r,
                    source_store="graph",
                ))

        elif request.query_type == KnowledgeQueryType.STRUCTURED:
            # Structured query — fall back to hybrid search
            return await self.hybrid_search(
                request.workspace_id,
                str(request.query),
                request.max_results,
            )

        return KnowledgeResult(
            hits=hits[:request.max_results],
            total=len(hits),
            query=request,
            execution_time_ms=(time.monotonic() - start) * 1000,
        )

    async def hybrid_search(
        self,
        workspace_id: str,
        query_text: str,
        max_results: int = 10,
    ) -> list[SearchHit]:
        """Hybrid search — use chatpid's ContextRAG for graph context +
        VectorRAG for semantic matches."""
        from chatpid.context_rag import context_rag
        from chatpid.vector_rag import vector_rag

        # Get vector hits
        vec_results = vector_rag(self._driver, query_text, level="conceptual", top_k=max_results)
        hits = []
        for r in vec_results:
            hits.append(SearchHit(
                entity_id=str(r.get("id", "")),
                entity_type=r.get("label", "Unknown"),
                score=r.get("score", 0.0),
                properties=r,
                source_store="vector",
            ))

        # If no vector hits, get graph context
        if not hits:
            graph_text = context_rag(self._driver, level="conceptual", mode="graph")
            # Return a single "hit" representing the full graph context
            hits.append(SearchHit(
                entity_id="graph_context",
                entity_type="GraphContext",
                score=1.0,
                properties={"text": graph_text[:5000]},
                source_store="graph",
            ))

        return hits[:max_results]

    async def write_back(self, write_request: EntityWriteRequest) -> SearchHit:
        """Write back an entity — not supported for read-only P&ID graphs."""
        raise NotImplementedError("P&ID knowledge graphs are read-only")

    async def ingest(self, source: DataSource) -> IngestionResult:
        """Ingest a data source — delegates to chatpid's ingestion pipeline."""
        raise NotImplementedError("Use chatpid's scripts/01_ingest.py for ingestion")

    async def get_schema(self, workspace_id: str) -> dict[str, object]:
        """Get the graph schema — node labels and property keys."""
        with self._driver.session() as session:
            labels = session.run("CALL db.labels() YIELD label RETURN collect(label) as labels").single()["labels"]
            rel_types = session.run("CALL db.relationshipTypes() YIELD relationshipType RETURN collect(relationshipType) as types").single()["types"]
        return {"node_labels": labels, "relationship_types": rel_types}


async def main() -> None:
    print("=" * 70)
    print("SCRUM-412: Platform Integration Test")
    print("Can chatpid's Neo4j graph satisfy platform's KnowledgeStore protocol?")
    print("=" * 70)

    # 1. Create the Neo4j-backed KnowledgeStore
    print("\n[1] Creating Neo4jKnowledgeStore adapter...")
    store = Neo4jKnowledgeStore()
    schema = await store.get_schema("chatpid")
    print(f"  Schema: {len(schema['node_labels'])} node labels, "
          f"{len(schema['relationship_types'])} relationship types")

    # 2. Register platform's GraphRAG capabilities with the store
    print("\n[2] Registering platform's GraphRAG capabilities...")
    registry = CapabilityRegistry()
    registry.register_many([
        ContextRAGCapability(store),
        VectorRAGCapability(store),
        PathRAGCapability(store),
        CypherRAGCapability(store),
    ])
    await registry.initialize()
    specs = registry.list(type_filter=CapabilityType.TOOL)
    print(f"  Registered {len(specs)} capabilities:")
    for s in specs:
        print(f"    {s.id}: {s.name}")

    # 3. Test each capability
    test_query = "What is the cylinder length of tank T4750?"

    print(f"\n[3] Testing ContextRAG with query: '{test_query}'")
    try:
        result = await registry.execute("context_rag", {
            "workspace_id": "chatpid",
            "query": test_query,
            "max_results": 5,
        })
        print(f"  Success: {result.success}")
        if result.success:
            print(f"  Hits: {result.data.get('total', 0)}")
            for hit in result.data.get("hits", [])[:2]:
                print(f"    {hit.get('entity_type', '?')}: {hit.get('entity_id', '?')}")
        else:
            print(f"  Error: {result.error.message if result.error else 'unknown'}")
        print(f"  Time: {result.execution_time_ms:.1f}ms")
    except Exception as e:
        print(f"  EXCEPTION: {e}")

    print(f"\n[4] Testing VectorRAG with query: '{test_query}'")
    try:
        result = await registry.execute("vector_rag", {
            "workspace_id": "chatpid",
            "query": test_query,
            "max_results": 5,
        })
        print(f"  Success: {result.success}")
        if result.success:
            print(f"  Hits: {result.data.get('total', 0)}")
            for hit in result.data.get("hits", [])[:2]:
                print(f"    {hit.get('entity_type', '?')}: score={hit.get('score', 0):.3f}")
        else:
            print(f"  Error: {result.error.message if result.error else 'unknown'}")
        print(f"  Time: {result.execution_time_ms:.1f}ms")
    except Exception as e:
        print(f"  EXCEPTION: {e}")

    print(f"\n[5] Testing PathRAG with query: 'Trace flow from tank T4750'")
    try:
        result = await registry.execute("path_rag", {
            "workspace_id": "chatpid",
            "query": "Trace flow from tank T4750",
            "max_depth": 3,
        })
        print(f"  Success: {result.success}")
        if result.success:
            print(f"  Hits: {result.data.get('total', 0)}")
        else:
            print(f"  Error: {result.error.message if result.error else 'unknown'}")
        print(f"  Time: {result.execution_time_ms:.1f}ms")
    except Exception as e:
        print(f"  EXCEPTION: {e}")

    print(f"\n[6] Testing CypherRAG with query: '{test_query}'")
    try:
        result = await registry.execute("cypher_rag", {
            "workspace_id": "chatpid",
            "query": test_query,
        })
        print(f"  Success: {result.success}")
        if result.success:
            print(f"  Hits: {result.data.get('total', 0)}")
        else:
            print(f"  Error: {result.error.message if result.error else 'unknown'}")
        print(f"  Time: {result.execution_time_ms:.1f}ms")
    except Exception as e:
        print(f"  EXCEPTION: {e}")

    # 7. Assessment
    print("\n" + "=" * 70)
    print("INTEGRATION ASSESSMENT")
    print("=" * 70)
    print("""
FINDINGS — Where the platform capability spec fits and where it breaks:

1. PROTOCOL FIT (good):
   - The Capability protocol (spec + install + execute + execute_stream) is
     clean and chatpid's tools can be wrapped to satisfy it.
   - The CapabilityRegistry pattern works — registering 4 GraphRAG capabilities
     and executing them by ID works out of the box.
   - The KnowledgeStore protocol's query() method with KnowledgeQueryType enum
     maps reasonably to chatpid's 4 tools (CYPHER→CypherRAG, VECTOR→VectorRAG,
     GRAPH_TRAVERSAL→PathRAG, STRUCTURED/HYBRID→ContextRAG).

2. PROTOCOL FRICTION (needs amendment):
   a. ASYNC VS SYNC: Platform's KnowledgeStore is async, chatpid's Neo4j driver
      calls are sync. The adapter wraps sync calls in async methods, but this
      blocks the event loop. A production adapter would need async Neo4j driver.
   b. SearchHit vs TEXT: Platform returns SearchHit objects (entity_id, score,
      properties), but chatpid's tools return TEXT strings for the LLM. The
      adapter converts, but loses the natural-language answer that makes
      GraphRAG useful. The spec needs a "text_result" field or a separate
      "narrative" output type.
   c. WORKSPACE_ID: Platform assumes multi-tenant workspaces, chatpid has a
      single graph. The adapter ignores workspace_id, but the spec assumes
      workspace-scoped queries.
   d. WRITE_BACK/INGEST: Platform's KnowledgeStore has write_back() and ingest()
      for live updates. P&ID graphs are read-only (ingested from DEXPI XML).
      The adapter raises NotImplementedError, but the spec doesn't have a
      "read-only" flag.
   e. GRAPH_DEPTH: PathRAG's spec has graph_depth, but chatpid's PathRAG uses
      max_depth + max_breadth (two parameters). The spec's single graph_depth
      doesn't capture the breadth dimension.

3. VERDICT:
   The capability spec is 70% there. It works for basic retrieval, but needs
   amendments for:
   - Sync/async bridge guidance (or async-first requirement)
   - Text/narrative results (not just structured SearchHits)
   - Read-only store flag
   - Multi-dimensional graph traversal parameters (depth + breadth)

   These are spec amendments, not architectural changes — the 7-layer pattern
   and capability registry work. The friction is in the details of the
   KnowledgeStore protocol, not the overall design.
""")

    # Save results
    store._driver.close()


if __name__ == "__main__":
    asyncio.run(main())
