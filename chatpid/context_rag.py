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

_NON_CONTENT_PROPS = {"level", "element_id"}


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

    query = """
    MATCH (n {level: $level})
    OPTIONAL MATCH (n)-[r {level: $level}]->(m {level: $level})
    RETURN labels(n) AS source_labels, n.tag AS source_tag, n AS source_props,
           type(r) AS relationship,
           labels(m) AS target_labels, m.tag AS target_tag
    """

    lines: list[str] = []
    with driver.session() as session:
        for record in session.run(query, level=level):
            source_labels = [
                l for l in (record["source_labels"] or []) if l != "Node"
            ]
            source = record["source_tag"] or "/".join(source_labels) or "Node"

            if mode == "graph":
                props = {
                    k: v
                    for k, v in dict(record["source_props"]).items()
                    if k not in _NON_CONTENT_PROPS and v is not None
                }
                source_repr = f"{source} {props}" if props else source
            else:
                source_repr = source

            if record["relationship"]:
                target_labels = [
                    l for l in (record["target_labels"] or []) if l != "Node"
                ]
                target = record["target_tag"] or "/".join(target_labels) or "Node"
                lines.append(f"{source_repr} --{record['relationship']}--> {target}")
            else:
                lines.append(source_repr)

    return "\n".join(dict.fromkeys(lines))  # de-dupe while preserving order
