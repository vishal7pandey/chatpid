"""ContextRAG: condensed, noise-free textual context from the knowledge graph.

The paper's best-performing tool overall (GPT-5-mini: 0.91 accuracy at
$0.004/task - Table 4) and the only tool fully implemented so far. Exports one
graph abstraction level from Neo4j and serializes it into compact text,
stripping internal ids/metadata the LLM doesn't need (Section 3.3.1).
"""

from __future__ import annotations

from neo4j import Driver

VALID_MODES = ("graph", "topology")
VALID_LEVELS = ("complete", "process", "conceptual")

# Properties that are internal metadata, not engineering content.
_NON_CONTENT_PROPS = {
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
    # Semantic enrichment + embedding properties (not for ContextRAG output)
    "global_semantic",
    "local_semantic",
    "global_semantic_embedding",
    "local_semantic_embedding",
}


def context_rag(driver: Driver, level: str = "conceptual", mode: str = "graph") -> str:
    """Return a compact text serialization of one graph abstraction level.

    Args:
        driver: an open Neo4j driver.
        level: "complete" | "process" | "conceptual" (paper default: conceptual).
        mode: "graph" keeps node/edge properties (tag, design specs, relationship
            type) for detailed reasoning; "topology" keeps only labels and
            connectivity for a lightweight structural overview.
    """
    if level not in VALID_LEVELS:
        raise ValueError(f"level must be one of {VALID_LEVELS}, got {level!r}")
    if mode not in VALID_MODES:
        raise ValueError(f"mode must be one of {VALID_MODES}, got {mode!r}")

    lines: list[str] = []

    with driver.session() as session:
        # --- Nodes: output each node once with its properties ---
        node_query = """
        MATCH (n {level: $level})
        RETURN n.tag AS tag, labels(n) AS labels, n AS props
        """
        for record in session.run(node_query, level=level):
            tag = record["tag"] or "Node"
            if mode == "graph":
                props = {
                    k: v
                    for k, v in dict(record["props"]).items()
                    if k not in _NON_CONTENT_PROPS and v is not None
                }
                if props:
                    # Compact property formatting: key=value pairs
                    prop_str = ", ".join(f"{k}={v}" for k, v in sorted(props.items()))
                    lines.append(f"[{tag}] {prop_str}")
                else:
                    lines.append(f"[{tag}]")
            else:
                lines.append(f"[{tag}]")

        # --- Edges: output each edge once ---
        edge_query = """
        MATCH (a {level: $level})-[r {level: $level}]->(b {level: $level})
        RETURN a.tag AS source, type(r) AS rel, b.tag AS target
        """
        for record in session.run(edge_query, level=level):
            source = record["source"] or "Node"
            target = record["target"] or "Node"
            rel = record["rel"] or "RELATED_TO"
            lines.append(f"{source} --{rel}--> {target}")

    return "\n".join(lines)
