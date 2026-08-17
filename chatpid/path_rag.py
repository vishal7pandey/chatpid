"""PathRAG: locate-and-trace path exploration retrieval (Algorithm 3, Section 3.3.3).

The paper's PathRAG uses VectorRAG (semantic embedding search) to find starting
nodes and select the next hop. Since we don't have embeddings yet (SCRUM-361/362
pending), this implementation uses text-based similarity (tag/label/property
matching) as a stand-in for VectorRAG. The path traversal logic — the core
algorithm — is identical. When embeddings are ready, swapping in VectorRAG for
the locate/next-hop steps is a one-function change.

Algorithm:
  1. Find starting nodes: text-match query against node tags/labels/properties
  2. From each starting node, traverse neighbors:
     a. Accumulate context from visited nodes
     b. Pick the most relevant unvisited neighbor (text-match or local VectorRAG)
     c. Repeat until max_depth reached or no unvisited neighbors
  3. Return all explored paths with accumulated context

The paper uses max_breadth=2, max_depth=3 for the small DEXPI P&ID.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from neo4j import Driver

# --- Text-based similarity (stand-in for VectorRAG) ---

def _tokenize(text: str) -> set[str]:
    """Simple tokenization for text matching."""
    return set(text.lower().replace("-", " ").replace("_", " ").split())


def _text_similarity(query_tokens: set[str], text: str) -> float:
    """Jaccard-like similarity between query tokens and a text string."""
    text_tokens = _tokenize(text)
    if not text_tokens or not query_tokens:
        return 0.0
    return len(query_tokens & text_tokens) / len(query_tokens | text_tokens)


def _node_text(node: dict) -> str:
    """Concatenate all text-relevant fields of a node into one string."""
    parts = [str(node.get("tag", ""))]
    label = node.get("label", "")
    if label:
        parts.append(label)
    # Include pipingComponentName if present (e.g. "66KL21")
    comp_name = node.get("pipingComponentName", "")
    if comp_name:
        parts.append(comp_name)
    return " ".join(parts)


# --- PathRAG core ---

@dataclass
class PathResult:
    """One explored path through the graph."""
    path: list[str]  # list of node tags
    nodes: list[dict]  # full node properties at each step
    edges: list[dict]  # edge types along the path
    context: str  # accumulated text context
    scores: list[float]  # relevance score at each hop


@dataclass
class PathRAGResult:
    """Full PathRAG result across all explored paths."""
    paths: list[PathResult]
    best_path: PathResult | None = None
    answer_context: str = ""


def find_starting_nodes(
    driver: Driver, query: str, level: str = "conceptual", max_breadth: int = 2
) -> list[dict]:
    """Find the most relevant starting nodes for a query.

    Uses text similarity against node tags/labels/properties as a stand-in
    for global VectorRAG. When embeddings are ready, replace this with:
        vector_rag(driver, query, "global_semantic_index", max_breadth)
    """
    query_tokens = _tokenize(query)
    cypher = """
    MATCH (n {level: $level})
    RETURN n.tag AS tag, labels(n) AS labels, n AS props
    """
    with driver.session() as session:
        nodes = []
        for record in session.run(cypher, level=level):
            props = dict(record["props"])
            # Remove internal metadata and embeddings (not needed for path traversal)
            for key in ("level", "element_id", "global_semantic_embedding", "local_semantic_embedding"):
                props.pop(key, None)
            label = [l for l in (record["labels"] or []) if l != "Node"]
            props["label"] = label[0] if label else ""
            text = _node_text(props)
            score = _text_similarity(query_tokens, text)
            nodes.append({**props, "tag": record["tag"], "_score": score})

    # Sort by score, return top max_breadth
    nodes.sort(key=lambda n: n["_score"], reverse=True)
    return nodes[:max_breadth]


def get_neighbors(
    driver: Driver, node_tag: str, level: str = "conceptual", direction: str = "both"
) -> list[dict]:
    """Get unvisited neighbors of a node. direction: 'in', 'out', or 'both'."""
    parts = []
    if direction in ("out", "both"):
        parts.append("""
            MATCH (n {tag: $tag, level: $level})-[r {level: $level}]->(m {level: $level})
            RETURN m.tag AS tag, labels(m) AS labels, m AS props,
                   type(r) AS rel_type, 'out' AS direction
        """)
    if direction in ("in", "both"):
        parts.append("""
            MATCH (n {tag: $tag, level: $level})<-[r {level: $level}]-(m {level: $level})
            RETURN m.tag AS tag, labels(m) AS labels, m AS props,
                   type(r) AS rel_type, 'in' AS direction
        """)
    cypher = " UNION ".join(parts)

    with driver.session() as session:
        neighbors = []
        for record in session.run(cypher, tag=node_tag, level=level):
            props = dict(record["props"])
            for key in ("level", "element_id", "global_semantic_embedding", "local_semantic_embedding"):
                props.pop(key, None)
            label = [l for l in (record["labels"] or []) if l != "Node"]
            props["label"] = label[0] if label else ""
            neighbors.append({
                **props,
                "tag": record["tag"],
                "rel_type": record["rel_type"],
                "direction": record["direction"],
            })
        return neighbors


# Properties that are internal metadata or embeddings, not engineering content.
# Must not be serialized into PathRAG output (embeddings are 384-dim float arrays
# that would waste thousands of tokens per node).
_NON_CONTENT_PROPS = {
    "tag",
    "label",
    "_score",
    "rel_type",
    "direction",
    "level",
    "element_id",
    "proteusId",
    "tagNamePrefix",
    "tagNameSequenceNumber",
    "tagNameSuffix",
    "nominalDiameterTypeRepresentation",
    "nominalDiameterNumericalValueRepresentation",
    "nominalDiameterStandard",
    "primarySecondaryPipingNetworkSegment",
    "collapsed_from",
    "collapsed_node_id",
    "stitched_from",
    "labels",
    "label_description",
    "global_semantic_embedding",
    "local_semantic_embedding",
    "global_semantic",
    "local_semantic",
}


def _format_node_context(node: dict) -> str:
    """Format a node's properties as readable context text."""
    tag = node.get("tag", "Node")
    label = node.get("label", "")
    parts = [f"[{tag}]"]
    if label:
        parts.append(f"({label})")
    # Include key engineering properties (exclude embeddings, semantic text, metadata)
    eng_props = {k: v for k, v in node.items() if k not in _NON_CONTENT_PROPS and v is not None}
    if eng_props:
        prop_str = ", ".join(f"{k}={v}" for k, v in sorted(eng_props.items()))
        parts.append(prop_str)
    return " ".join(parts)


def path_rag(
    driver: Driver,
    query: str,
    level: str = "conceptual",
    max_depth: int = 3,
    max_breadth: int = 2,
) -> PathRAGResult:
    """Trace paths through the graph to answer `query`.

    Mirrors Algorithm 3 of the paper. Uses text similarity instead of
    VectorRAG for starting-node selection and next-hop selection.

    Args:
        query: natural language question
        level: graph abstraction level
        max_depth: max hops per path (paper uses 3)
        max_breadth: max parallel starting paths (paper uses 2)
    """
    query_tokens = _tokenize(query)

    # Step 1: Find starting nodes
    starting_nodes = find_starting_nodes(driver, query, level, max_breadth)
    if not starting_nodes:
        return PathRAGResult(paths=[], best_path=None, answer_context="No relevant nodes found.")

    all_paths: list[PathResult] = []

    # Step 2: Expand paths from each starting node
    for start_node in starting_nodes:
        path_tags = [start_node["tag"]]
        path_nodes = [start_node]
        path_edges: list[dict] = []
        contexts = [_format_node_context(start_node)]
        scores = [start_node["_score"]]
        visited = {start_node["tag"]}
        current = start_node

        for depth in range(max_depth):
            # Get unvisited neighbors
            neighbors = get_neighbors(driver, current["tag"], level)
            neighbors = [n for n in neighbors if n["tag"] not in visited]

            if not neighbors:
                break

            # Score neighbors by text similarity to query
            for n in neighbors:
                n["_score"] = _text_similarity(query_tokens, _node_text(n))

            # Pick the most relevant neighbor
            neighbors.sort(key=lambda n: n["_score"], reverse=True)
            next_node = neighbors[0]

            # Record edge
            path_edges.append({
                "from": current["tag"],
                "to": next_node["tag"],
                "type": next_node["rel_type"],
                "direction": next_node["direction"],
            })

            # Advance
            path_tags.append(next_node["tag"])
            path_nodes.append({k: v for k, v in next_node.items()})
            contexts.append(_format_node_context(next_node))
            scores.append(next_node["_score"])
            visited.add(next_node["tag"])
            current = next_node

        # Build accumulated context
        acc_context = "\n".join(contexts)
        path_result = PathResult(
            path=path_tags,
            nodes=path_nodes,
            edges=path_edges,
            context=acc_context,
            scores=scores,
        )
        all_paths.append(path_result)

    # Step 3: Select best path (highest average score)
    best = max(all_paths, key=lambda p: sum(p.scores) / len(p.scores)) if all_paths else None
    best_context = best.context if best else ""

    return PathRAGResult(paths=all_paths, best_path=best, answer_context=best_context)


def path_rag_text(driver: Driver, query: str, level: str = "conceptual",
                   max_depth: int = 3, max_breadth: int = 2) -> str:
    """Convenience wrapper: return PathRAG result as formatted text for LLM consumption."""
    result = path_rag(driver, query, level, max_depth, max_breadth)
    if not result.paths:
        return "No relevant path found in the graph."

    lines = []
    for i, p in enumerate(result.paths):
        lines.append(f"--- Path {i+1} (score: {sum(p.scores)/len(p.scores):.3f}) ---")
        # Path summary
        path_str = " -> ".join(p.path)
        lines.append(f"Path: {path_str}")
        # Edges
        for e in p.edges:
            arrow = "-->" if e["direction"] == "out" else "<--"
            lines.append(f"  {e['from']} {arrow} {e['to']} ({e['type']})")
        # Node details
        lines.append("Nodes:")
        for node in p.nodes:
            lines.append(f"  {_format_node_context(node)}")
        lines.append("")

    if result.best_path:
        lines.append(f"Best path: {' -> '.join(result.best_path.path)}")

    return "\n".join(lines)
