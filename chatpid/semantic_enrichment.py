"""Semantic enrichment: generate global + local text descriptions for every node.

Implements Algorithm 1 from the paper (Section 3.2.2). For each node:
  - global_semantic: the node's functional role in the whole flowsheet
  - local_semantic: the node's role relative to its immediate neighbors

These descriptions are embedded and used by VectorRAG and PathRAG for
semantic similarity search.

The descriptions are written back onto the Neo4j nodes as properties
`global_semantic` and `local_semantic` so downstream tools can use them.
"""

from __future__ import annotations

import logging
import time
from dataclasses import dataclass

from neo4j import Driver

logger = logging.getLogger(__name__)

from chatpid.context_rag import context_rag
from chatpid.llm import get_llm

GLOBAL_SEMANTIC_PROMPT = """\
You are a process engineering assistant.
Describe the role and function of this node in the process flowsheet \
(global context), based on given information.
Focus on what the equipment/component does, using its name or tag (not IDs). \
Be clear and concise. One to two sentences max.

Node:
Labels: {labels}
Properties: {properties}

Flowsheet context:
{flowsheet_representation}
"""

LOCAL_SEMANTIC_PROMPT = """\
You are a process engineering assistant.
Describe the local context of this node in the process flowsheet, focusing on \
its immediate relationships. Use the node's labels and properties, and explain \
how it connects to its neighbors. Focus on what the equipment/component does, \
using its name or tag (not IDs). Be clear and concise. One to two sentences max.

Central Node:
Labels: {node_labels}
Properties: {node_properties}

Incoming Connections:
{incoming_connections}

Outgoing Connections:
{outgoing_connections}
"""


@dataclass
class NodeSemantics:
    element_id: str
    tag: str
    global_semantic: str
    local_semantic: str


def _get_all_nodes(driver: Driver, level: str) -> list[dict]:
    """Fetch all nodes at a given level with their properties."""
    with driver.session() as session:
        result = session.run(
            "MATCH (n {level: $level}) RETURN elementId(n) AS eid, n.tag AS tag, labels(n) AS labels, n AS props",
            level=level,
        )
        nodes = []
        for record in result:
            props = dict(record["props"])
            props.pop("level", None)
            props.pop("element_id", None)
            labels = [l for l in record["labels"] if l != "Node"]
            nodes.append(
                {
                    "element_id": record["eid"],
                    "tag": record["tag"],
                    "labels": labels,
                    "properties": props,
                }
            )
        return nodes


def _get_neighbors_text(driver: Driver, tag: str, level: str) -> tuple[str, str]:
    """Get formatted incoming and outgoing connection text for a node."""
    with driver.session() as session:
        # Outgoing
        out_result = session.run(
            """
            MATCH (n {tag: $tag, level: $level})-[r {level: $level}]->(m {level: $level})
            RETURN m.tag AS neighbor_tag, labels(m) AS neighbor_labels,
                   type(r) AS rel_type, m AS neighbor_props
            """,
            tag=tag,
            level=level,
        )
        out_lines = []
        for record in out_result:
            nlabels = [l for l in record["neighbor_labels"] if l != "Node"]
            out_lines.append(
                f"  -> [{record['neighbor_tag']}] ({', '.join(nlabels)}) via {record['rel_type']}"
            )

        # Incoming
        in_result = session.run(
            """
            MATCH (n {tag: $tag, level: $level})<-[r {level: $level}]-(m {level: $level})
            RETURN m.tag AS neighbor_tag, labels(m) AS neighbor_labels,
                   type(r) AS rel_type, m AS neighbor_props
            """,
            tag=tag,
            level=level,
        )
        in_lines = []
        for record in in_result:
            nlabels = [l for l in record["neighbor_labels"] if l != "Node"]
            in_lines.append(
                f"  <- [{record['neighbor_tag']}] ({', '.join(nlabels)}) via {record['rel_type']}"
            )

        incoming = "\n".join(in_lines) if in_lines else "  (none)"
        outgoing = "\n".join(out_lines) if out_lines else "  (none)"
        return incoming, outgoing


def _write_semantics(
    driver: Driver, element_id: str, global_sem: str, local_sem: str
) -> None:
    """Write semantic descriptions back onto a node."""
    with driver.session() as session:
        session.run(
            """
            MATCH (n) WHERE elementId(n) = $eid
            SET n.global_semantic = $global_sem,
                n.local_semantic = $local_sem
            """,
            eid=element_id,
            global_sem=global_sem,
            local_sem=local_sem,
        )


def enrich_all_nodes(
    driver: Driver,
    level: str = "conceptual",
    delay: float = 0.0,
    verbose: bool = True,
) -> list[NodeSemantics]:
    """Generate global+local semantics for every node at `level`.

    Uses ContextRAG's topology output as the flowsheet representation for
    global context. For each node, calls the LLM twice (global + local),
    then writes the results back to Neo4j.

    Args:
        level: graph abstraction level
        delay: seconds to wait between LLM calls (rate-limit protection)
        verbose: print progress
    """
    llm = get_llm(temperature=0)

    # Get flowsheet representation for global context
    flowsheet_repr = context_rag(driver, level=level, mode="topology")

    # Get all nodes
    nodes = _get_all_nodes(driver, level)
    if verbose:
        print(f"Enriching {len(nodes)} nodes at level='{level}'...")

    results: list[NodeSemantics] = []

    for i, node in enumerate(nodes):
        tag = node["tag"] or node["element_id"]
        labels = node["labels"]
        props = node["properties"]

        if verbose:
            print(
                f"  [{i + 1}/{len(nodes)}] {tag} ({', '.join(labels)})...",
                end=" ",
                flush=True,
            )

        try:
            # Global semantic
            global_prompt = GLOBAL_SEMANTIC_PROMPT.format(
                labels=labels,
                properties=props,
                flowsheet_representation=flowsheet_repr[:3000],  # cap context
            )
            global_sem = llm.invoke(global_prompt).content.strip()

            if delay > 0:
                time.sleep(delay)

            # Local semantic
            incoming, outgoing = _get_neighbors_text(driver, tag, level)
            local_prompt = LOCAL_SEMANTIC_PROMPT.format(
                node_labels=labels,
                node_properties=props,
                incoming_connections=incoming,
                outgoing_connections=outgoing,
            )
            local_sem = llm.invoke(local_prompt).content.strip()

            # Write back to Neo4j
            _write_semantics(driver, node["element_id"], global_sem, local_sem)

            results.append(
                NodeSemantics(
                    element_id=node["element_id"],
                    tag=tag,
                    global_semantic=global_sem,
                    local_semantic=local_sem,
                )
            )

            if verbose:
                print(f"OK ({len(global_sem)} + {len(local_sem)} chars)")

        except Exception as exc:
            if verbose:
                print(f"ERROR: {exc!s:.100}")
            results.append(
                NodeSemantics(
                    element_id=node["element_id"],
                    tag=tag,
                    global_semantic="",
                    local_semantic=f"ERROR: {exc}",
                )
            )

        if delay > 0:
            time.sleep(delay)

    if verbose:
        ok = sum(
            1
            for r in results
            if r.global_semantic and not r.local_semantic.startswith("ERROR")
        )
        print(f"Done: {ok}/{len(nodes)} nodes enriched successfully")

    return results
