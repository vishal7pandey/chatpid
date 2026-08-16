"""DEXPI ingestion: load XML -> pyDEXPI -> 3 graph levels -> Neo4j.

Flattened from the old ingestion/{load_dexpi,build_graphs,load_to_neo4j}.py.
The pyDEXPI wrapper calls and the Neo4j loader logic are the only parts of the
scaffold worth preserving as-is (per SCRUM-355); everything else in the project
is flat scripts built on top of this.

Mirrors Section 3.2.1 of the ChatP&ID paper. pyDEXPI ships the condensation
logic (GraphAbstractor), so this is a thin wrapper:

  complete   - one-to-one mapping of every pyDEXPI entity/relationship
  process    - condenses the piping system (segments/fittings collapsed)
  conceptual - further condenses piping, instrumentation, and equipment

The paper's headline result (GPT-5: 0.94 accuracy at $0.027/task) used the
conceptual graph, so default to that unless a task needs finer detail.
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import networkx as nx
from neo4j import Driver, GraphDatabase
from pydexpi.loaders import GraphAbstractor, GraphLoader, ProteusSerializer

from chatpid.config import get_settings


# --- Step 1: DEXPI/Proteus XML -> pyDEXPI model -----------------------------


def load_dexpi_model(directory: str | Path, filename: str) -> Any:
    """Load a Proteus XML export into a pyDEXPI DexpiModel instance.

    pyDEXPI's loader takes a directory + filename pair, not a single path.
    """
    return ProteusSerializer().load(str(directory), filename)


# --- Step 2: pyDEXPI model -> three graph abstraction levels ----------------


@dataclass
class FlowsheetGraphs:
    complete: Any
    process: Any
    conceptual: Any


def build_graph_abstractions(dexpi_model: Any) -> FlowsheetGraphs:
    """Convert a pyDEXPI model into complete/process/conceptual NetworkX graphs."""
    plant_graph = GraphLoader().parse_dexpi_to_graph(dexpi_model)
    return FlowsheetGraphs(
        complete=GraphAbstractor.build_complete_graph(plant_graph),
        process=GraphAbstractor.build_process_graph(plant_graph),
        conceptual=GraphAbstractor.build_conceptual_graph(plant_graph),
    )


# --- Step 3: NetworkX graph -> Neo4j ---------------------------------------


def get_driver() -> Driver:
    settings = get_settings()
    return GraphDatabase.driver(
        settings.neo4j_uri, auth=(settings.neo4j_user, settings.neo4j_password)
    )


def _serialize_value(value: Any) -> Any:
    """Neo4j properties must be primitives or lists of primitives."""
    if value is None or isinstance(value, (str, int, float, bool)):
        return value
    return json.dumps(value, default=str)


def _safe_label(raw: Any) -> str:
    text = str(raw) if raw else "Node"
    cleaned = "".join(c for c in text if c.isalnum() or c == "_")
    return cleaned or "Node"


def _safe_rel_type(raw: Any) -> str:
    text = str(raw) if raw else "RELATED_TO"
    cleaned = "".join(c if c.isalnum() else "_" for c in text).strip("_").upper()
    return cleaned or "RELATED_TO"


def clear_level(driver: Driver, level: str) -> None:
    """Delete all nodes/relationships previously loaded for this abstraction level."""
    with driver.session() as session:
        session.run("MATCH (n {level: $level}) DETACH DELETE n", level=level)


def load_graph(driver: Driver, graph: nx.MultiDiGraph, level: str) -> None:
    """Merge a NetworkX graph into Neo4j under the given abstraction level.

    Re-running this for the same `level` first clears prior data for that level,
    so ingestion is idempotent. Each node/relationship is tagged with a `level`
    property so all three abstractions coexist in one database.

    NOTE: defensive, generic NetworkX -> Neo4j mapper. Has not yet been run
    against real pyDEXPI output — the attribute-name fallbacks (`labels`,
    `type`, `tag`) may need adjusting once you inspect
    graph.nodes(data=True) / graph.edges(data=True) for the actual schema
    GraphAbstractor produces. First thing to verify (SCRUM-356).
    """
    clear_level(driver, level)

    with driver.session() as session:
        for node_id, data in graph.nodes(data=True):
            raw_labels = data.get("labels") or [data.get("type", "Node")]
            # Every node also gets the generic `Node` label so tools (vector
            # indexes, ContextRAG, etc.) can query across all pyDEXPI classes
            # without enumerating them.
            label_str = ":".join(
                dict.fromkeys(["Node", *(_safe_label(l) for l in raw_labels)])
            )
            props = {k: _serialize_value(v) for k, v in data.items() if k != "labels"}
            props["element_id"] = str(node_id)
            props["level"] = level
            session.run(
                f"MERGE (n:{label_str} {{element_id: $element_id, level: $level}}) "
                f"SET n += $props",
                element_id=str(node_id),
                level=level,
                props=props,
            )

        for source, target, data in graph.edges(data=True):
            rel_type = _safe_rel_type(data.get("type") or data.get("label"))
            props = {k: _serialize_value(v) for k, v in data.items()}
            props["level"] = level
            session.run(
                f"""
                MATCH (a {{element_id: $source, level: $level}})
                MATCH (b {{element_id: $target, level: $level}})
                MERGE (a)-[r:{rel_type}]->(b)
                SET r += $props
                """,
                source=str(source),
                target=str(target),
                level=level,
                props=props,
            )
