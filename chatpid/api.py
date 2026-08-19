"""Minimal FastAPI wrapper for ChatP&ID — exposes the agent and graph over HTTP.

SCRUM-391: Thin wrapper around agent.py/ingest.py. Two endpoints:
  POST /ask  — takes a question, calls the agent, returns answer + tool usage
  GET  /graph — returns node/edge data for graph visualization

Run:
    uv run uvicorn chatpid.api:app --reload --port 8000
"""

from __future__ import annotations

import threading
import time
from typing import Any

import tempfile
import uuid
from pathlib import Path

from fastapi import FastAPI, HTTPException, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

from chatpid.agent import build_agent
from chatpid.ingest import build_graph_abstractions, get_driver, load_dexpi_model, load_graph
from pydexpi.loaders import ProteusSerializer
from pydexpi.loaders.svg_loader import DrawDiagram

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

# Per-request state for /graph highlighting — protected by a lock to
# prevent concurrent /ask requests from overwriting each other.
_state_lock = threading.Lock()
_last_question: str = ""
_last_answer: str = ""
_last_tools: list[dict] = []
_last_graph_nodes: list[str] = []  # node IDs touched by last answer


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
                tools_used.append({
                    "name": tc.get("name", "?"),
                    "args": tc.get("args", {}),
                })
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
            tags = re.findall(r'\b[TPHV]\d{3,5}\b|\b\d{2}[A-Z]{2}\d{2}\b|\bSV\s?\d+\.\d+\b|\bC[1-9]\b', content)
            touched.update(tags)
    return list(touched)


# --- Request/Response models ---

class AskRequest(BaseModel):
    question: str
    level: str = "conceptual"


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
    global _last_question, _last_answer, _last_tools, _last_graph_nodes

    agent, _ = _ensure_agent()

    t0 = time.time()
    result = agent.invoke(
        {"messages": [{"role": "user", "content": req.question}]},
        config={"recursion_limit": 25},
    )
    elapsed = time.time() - t0

    messages = result.get("messages", [])
    answer = _extract_final_answer(messages)
    tools_used = _extract_tool_usage(messages)
    touched = _extract_touched_nodes(messages)

    # Cache for /graph endpoint (locked to prevent race between concurrent requests)
    with _state_lock:
        _last_question = req.question
        _last_answer = answer
        _last_tools = tools_used
        _last_graph_nodes = touched

    return AskResponse(
        answer=answer,
        tools_used=tools_used,
        latency_seconds=round(elapsed, 2),
        graph_node_ids=touched,
    )


@app.get("/graph", response_model=GraphResponse)
def get_graph(level: str = "conceptual", limit: int = 200, document_id: str = "") -> GraphResponse:
    """Return node/edge data for graph visualization.

    If the /ask endpoint was called recently, highlights nodes touched by
    the last answer. Otherwise returns a level-filtered slice of the graph.
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
        node_result = session.run(node_query, level=level, limit=limit, document_id=document_id or None)

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

            nodes.append(GraphNode(
                id=node_id,
                label=labels[0] if labels else "Node",
                tags=[tag] if tag else [],
                properties={"name": name, **props} if name else props,
            ))

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
        raise HTTPException(status_code=400, detail="File must be a .xml (DEXPI/Proteus) file")

    _, driver = _ensure_agent()
    document_id = str(uuid.uuid4())[:8]

    with tempfile.TemporaryDirectory() as tmpdir:
        tmp_path = Path(tmpdir) / file.filename
        content = await file.read()
        tmp_path.write_bytes(content)

        try:
            model = load_dexpi_model(tmpdir, file.filename)
        except Exception as exc:
            raise HTTPException(status_code=400, detail=f"Failed to parse DEXPI file: {exc}")

        graphs = build_graph_abstractions(model)
        levels_info = {}
        for level in ("complete", "process", "conceptual"):
            g = getattr(graphs, level)
            load_graph(driver, g, level, document_id=document_id)
            levels_info[level] = {"nodes": g.number_of_nodes(), "edges": g.number_of_edges()}

    return IngestResponse(document_id=document_id, levels=levels_info)


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
    import os
    from fastapi import Response

    search_dirs = ["data/dexpi_real", "data/raw"]
    found_path = None
    for d in search_dirs:
        candidate = os.path.join(d, filename)
        if os.path.isfile(candidate):
            found_path = d
            break

    if not found_path:
        raise HTTPException(
            status_code=404,
            detail=f"File '{filename}' not found in data/dexpi_real/ or data/raw/",
        )

    try:
        model = ProteusSerializer().load(found_path, filename)
        drawer = DrawDiagram(model.diagram, padding=5.0, pretty=True)
        # Render to in-memory SVG string
        import io
        import xml.etree.ElementTree as ET

        buf = io.StringIO()
        drawer.save_svg(os.path.splitext(filename)[0], buf)
        svg_content = buf.getvalue()
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"SVG rendering failed: {exc}")

    return Response(content=svg_content, media_type="image/svg+xml")


@app.get("/pid/files")
def list_pid_files() -> dict:
    """List available DEXPI P&ID files that can be rendered."""
    import os
    import glob

    files = []
    for d in ["data/dexpi_real", "data/raw"]:
        if os.path.isdir(d):
            for f in sorted(glob.glob(os.path.join(d, "*.xml"))):
                files.append({
                    "filename": os.path.basename(f),
                    "directory": d,
                })
    return {"files": files}


@app.get("/health")
def health() -> dict:
    """Health check."""
    return {"status": "ok", "model": "chatpid-api"}
