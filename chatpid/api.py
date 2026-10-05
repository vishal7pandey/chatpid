"""Minimal FastAPI wrapper for ChatP&ID — exposes the agent and graph over HTTP.

Thin wrapper around agent.py/ingest.py. Two endpoints:
  POST /ask  — takes a question, calls the agent, returns answer + tool usage
  GET  /graph — returns node/edge data for graph visualization

Run:
    uv run uvicorn chatpid.api:app --reload --port 8000
"""

from __future__ import annotations

import logging
import os
import tempfile
import time
import uuid
from pathlib import Path
from typing import Any

from fastapi import FastAPI, HTTPException, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from pydexpi.loaders import ProteusSerializer
from pydexpi.loaders.svg_loader import DrawDiagram

from chatpid.agent import build_agent
from chatpid.ingest import (
    build_graph_abstractions,
    get_driver,
    load_dexpi_model,
    load_graph,
)
from chatpid.logging_config import configure_logging

logger = logging.getLogger(__name__)

configure_logging()

app = FastAPI(title="ChatP&ID API", version="0.1.0")

# Allow the Next.js frontend (port 3000) to call this API
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000", "http://127.0.0.1:3000"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Module-level singletons — built once on startup, reused across requests.
_driver = None
_agent = None

# No per-request state lives in this module (CPID-14): /ask returns everything the client needs, including
# the touched node tags in `graph_node_ids`, and the client does its own highlighting.


def _ensure_agent():
    global _driver, _agent
    if _driver is None:
        _driver = get_driver()
    if _agent is None:
        _agent = build_agent(_driver)
    return _agent, _driver


def _extract_tool_usage(messages: list) -> list[dict]:
    """Extract which tools were called from the agent's message chain."""
    tools_used = []
    for msg in messages:
        # AIMessage with tool_calls
        tool_calls = getattr(msg, "tool_calls", None)
        if tool_calls:
            for tc in tool_calls:
                tools_used.append(
                    {
                        "name": tc.get("name", "?"),
                        "args": tc.get("args", {}),
                    }
                )
    return tools_used


def _extract_final_answer(messages: list) -> str:
    """Walk backward through the message chain to find the last AIMessage.

    Returns its content. If no AIMessage is found (e.g., chain ended on a
    ToolMessage due to an error), returns a clear error message instead of
    surfacing raw tool output as the answer.
    """
    for msg in reversed(messages):
        if "AIMessage" in type(msg).__name__:
            return msg.content if isinstance(msg.content, str) else str(msg.content)
    return "The agent did not produce a final answer. The last step may have failed — try rephrasing your question."


def _extract_touched_nodes(messages: list) -> list[str]:
    """Extract node tags/IDs mentioned in tool responses."""
    touched = set()
    for msg in messages:
        # ToolMessage contains the tool's output
        if hasattr(msg, "content") and "ToolMessage" in type(msg).__name__:
            content = msg.content if isinstance(msg.content, str) else str(msg.content)
            # Look for tag patterns like T4750, P4711, H1007, 66KL21, SV 104.01, C1-C4
            import re

            tags = re.findall(
                r"\b[TPHV]\d{3,5}\b|\b\d{2}[A-Z]{2}\d{2}\b|\bSV\s?\d+\.\d+\b|\bC[1-9]\b",
                content,
            )
            touched.update(tags)
    return list(touched)


GENERIC_LABELS = {
    "Node",
    "CustomAttributeOwner",
    "TechnicalItem",
    "PipingNodeOwner",
    "PipingSourceItem",
    "PipingTargetItem",
    "PipingNetworkSegmentItem",
    "PipingComponent",
    "SensingLocation",
    "SignalConveyingFunctionSource",
    "SignalConveyingFunctionTarget",
    "PlantSystemLocatedStructure",
    "PlantAreaLocatedStructure",
    "PlantTrainLocatedStructure",
    "ChamberOwner",
    "TaggedPlantItem",
    "NozzleOwner",
    "Equipment",
    "PipeFitting",
    "PipeOffPageConnector",
}


def _select_primary_label(labels: list[str]) -> str:
    """Pick the most specific domain label from a node's label hierarchy."""
    specific = [l for l in labels if l not in GENERIC_LABELS]
    return specific[-1] if specific else (labels[0] if labels else "Node")


# --- Request/Response models ---


class AskRequest(BaseModel):
    question: str
    level: str = "conceptual"
    document_id: str = ""


class AskResponse(BaseModel):
    answer: str
    tools_used: list[dict]
    latency_seconds: float
    graph_node_ids: list[str]


class GraphNode(BaseModel):
    id: str
    label: str
    tags: list[str]
    properties: dict


class GraphEdge(BaseModel):
    source: str
    target: str
    type: str


class GraphResponse(BaseModel):
    nodes: list[GraphNode]
    edges: list[GraphEdge]
    level: str
    total_nodes: int


# --- Endpoints ---


@app.post("/ask", response_model=AskResponse)
def ask(req: AskRequest) -> AskResponse:
    """Ask the ChatP&ID agent a question."""
    agent, _ = _ensure_agent()

    # Prefix user question with requested scope if provided
    context_prefixes = []
    if req.document_id:
        context_prefixes.append(f"[Target P&ID: {req.document_id}]")
    if req.level:
        context_prefixes.append(f"[Graph abstraction level: {req.level}]")

    prompt_content = (
        f"{' '.join(context_prefixes)} {req.question}"
        if context_prefixes
        else req.question
    )

    t0 = time.time()
    result = agent.invoke(
        {"messages": [{"role": "user", "content": prompt_content}]},
        config={"recursion_limit": 25},
    )
    elapsed = time.time() - t0

    messages = result.get("messages", [])
    answer = _extract_final_answer(messages)
    tools_used = _extract_tool_usage(messages)
    touched = _extract_touched_nodes(messages)

    logger.info(
        "ask: tools=%s nodes_touched=%d elapsed=%.2fs",
        [t["name"] for t in tools_used],
        len(touched),
        elapsed,
    )

    return AskResponse(
        answer=answer,
        tools_used=tools_used,
        latency_seconds=round(elapsed, 2),
        graph_node_ids=touched,
    )


@app.get("/graph", response_model=GraphResponse)
def get_graph(
    level: str = "conceptual", limit: int = 200, document_id: str = ""
) -> GraphResponse:
    """Return node/edge data for graph visualization.

    Returns a level-filtered slice of the graph; the result depends only on
    the request parameters. Highlighting is done by the client from the
    `graph_node_ids` that /ask returned.
    Pass document_id to scope to a specific uploaded document.
    """
    _, driver = _ensure_agent()

    with driver.session() as session:
        # Get nodes — filter by document_id if provided
        if document_id:
            node_query = """
                MATCH (n {level: $level, document_id: $document_id})
                WITH n LIMIT $limit
                RETURN elementId(n) AS id,
                       labels(n) AS labels,
                       n.tag AS tag,
                       n.name AS name,
                       properties(n) AS props
            """
        else:
            node_query = """
                MATCH (n {level: $level})
                WITH n LIMIT $limit
                RETURN elementId(n) AS id,
                       labels(n) AS labels,
                       n.tag AS tag,
                       n.name AS name,
                       properties(n) AS props
            """
        node_result = session.run(
            node_query, level=level, limit=limit, document_id=document_id or None
        )

        nodes = []
        node_ids = []
        for record in node_result:
            node_id = record["id"]
            node_ids.append(node_id)
            labels = record["labels"]
            tag = record["tag"] or ""
            name = record["name"] or ""
            props = dict(record["props"])
            # Remove large/embedding fields
            props.pop("embedding", None)
            props.pop("level", None)

            nodes.append(
                GraphNode(
                    id=node_id,
                    label=_select_primary_label(labels),
                    tags=[tag] if tag else [],
                    properties={"name": name, **props} if name else props,
                )
            )

        # Get edges between those nodes
        edge_result = session.run(
            """
            MATCH (a)-[r]->(b)
            WHERE elementId(a) IN $ids AND elementId(b) IN $ids
            RETURN elementId(a) AS source, elementId(b) AS target, type(r) AS type
            LIMIT 500
            """,
            ids=node_ids,
        )

        edges = [
            GraphEdge(source=r["source"], target=r["target"], type=r["type"])
            for r in edge_result
        ]

    return GraphResponse(
        nodes=nodes,
        edges=edges,
        level=level,
        total_nodes=len(nodes),
    )


# The upload is always written under this fixed name; the client's filename is only validated, never used
# as a path (CPID-20).
UPLOAD_TMP_NAME = "upload.xml"


def _is_plain_xml_name(filename: str) -> bool:
    """True only for a bare `*.xml` file name: no path separators, drive/stream colon, NUL or `..`."""
    return (
        filename.lower().endswith(".xml")
        and ".." not in filename
        and not any(ch in filename for ch in "/\\:\x00")
    )


class IngestResponse(BaseModel):
    document_id: str
    levels: dict  # level -> {"nodes": int, "edges": int}


@app.post("/ingest", response_model=IngestResponse)
async def ingest_document(file: UploadFile) -> IngestResponse:
    """Ingest a DEXPI/Proteus XML file into the knowledge graph.

    Accepts a .xml file upload, parses it with pyDEXPI, builds all 3
    graph abstraction levels, and loads them into Neo4j scoped by a
    unique document_id so multiple documents can coexist.
    """
    if not file.filename or not file.filename.endswith(".xml"):
        raise HTTPException(
            status_code=400, detail="File must be a .xml (DEXPI/Proteus) file"
        )
    if not _is_plain_xml_name(file.filename):
        raise HTTPException(status_code=400, detail="Invalid upload file name")

    _, driver = _ensure_agent()
    document_id = str(uuid.uuid4())[:8]

    with tempfile.TemporaryDirectory() as tmpdir:
        tmp_path = Path(tmpdir) / UPLOAD_TMP_NAME
        content = await file.read()
        tmp_path.write_bytes(content)

        try:
            model = load_dexpi_model(tmpdir, UPLOAD_TMP_NAME)
        except Exception:
            # Parser text can carry filesystem paths; the client only gets a generic message,
            # but the full traceback (including the path) goes to the log.
            logger.warning("ingest: failed to parse uploaded DEXPI file", exc_info=True)
            raise HTTPException(
                status_code=400, detail="Failed to parse DEXPI file"
            ) from None

        graphs = build_graph_abstractions(model)
        levels_info = {}
        for level in ("complete", "process", "conceptual"):
            g = getattr(graphs, level)
            load_graph(driver, g, level, document_id=document_id)
            levels_info[level] = {
                "nodes": g.number_of_nodes(),
                "edges": g.number_of_edges(),
            }

    return IngestResponse(document_id=document_id, levels=levels_info)


PID_SEARCH_DIRS = ("data/dexpi_real", "data/raw")


def _find_pid_dir(filename: str) -> str | None:
    """Return the allowed directory that really contains `filename`, or None.

    The resolved path (symlinks followed) must lie inside the resolved allowed
    directory BEFORE the filesystem is probed, so neither a traversal nor a
    symlink pointing outside is stat'ed or served (CPID-34, CPID-35).
    """
    for d in PID_SEARCH_DIRS:
        base = os.path.realpath(d)
        candidate = os.path.realpath(os.path.join(base, filename))
        if not candidate.startswith(base + os.sep):
            continue
        if os.path.isfile(candidate):
            return d
    return None


@app.get("/pid/svg")
def get_pid_svg(filename: str = "") -> Any:
    """Render a DEXPI P&ID diagram to SVG.

    Looks for the file in data/dexpi_real/ (downloaded test cases) or
    data/raw/ (original reference P&ID). Returns the SVG as
    image/svg+xml.

    Uses pyDEXPI's DrawDiagram renderer, which converts DEXPI graphical
    primitives (polylines, polygons, ellipses, arcs, text) to SVG elements
    with proper coordinate conversion (DEXPI Y-up → SVG Y-down).
    """
    from fastapi import Response

    if not _is_plain_xml_name(filename):
        raise HTTPException(status_code=400, detail="Invalid P&ID file name")

    found_path = _find_pid_dir(filename)
    if found_path is None:
        raise HTTPException(status_code=404, detail="P&ID file not found")

    try:
        model = ProteusSerializer().load(found_path, filename)
        drawer = DrawDiagram(model.diagram, padding=5.0, pretty=True)
        svg_content = drawer.draw_svg()
    except Exception:
        # Exception text can carry filesystem paths, so the client only gets a generic message.
        raise HTTPException(status_code=500, detail="SVG rendering failed") from None

    return Response(content=svg_content, media_type="image/svg+xml")


@app.get("/pid/files")
def list_pid_files() -> dict:
    """List available DEXPI P&ID files that can be rendered."""
    import glob
    import os

    files = []
    seen = set()
    for d in ["data/dexpi_real", "data/raw"]:
        if os.path.isdir(d):
            for f in sorted(glob.glob(os.path.join(d, "*.xml"))):
                filename = os.path.basename(f)
                if filename not in seen:
                    seen.add(filename)
                    files.append(
                        {
                            "filename": filename,
                            "directory": d,
                        }
                    )
    return {"files": files}


@app.get("/health")
def health() -> dict:
    """Health check."""
    return {"status": "ok", "model": "chatpid-api"}
