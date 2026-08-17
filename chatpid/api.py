"""Minimal FastAPI wrapper for ChatP&ID — exposes the agent and graph over HTTP.

SCRUM-391: Thin wrapper around agent.py/ingest.py. Two endpoints:
  POST /ask  — takes a question, calls the agent, returns answer + tool usage
  GET  /graph — returns node/edge data for graph visualization

Run:
    uv run uvicorn chatpid.api:app --reload --port 8000
"""

from __future__ import annotations

import time
from typing import Any

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

from chatpid.agent import build_agent
from chatpid.ingest import get_driver

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
    answer = messages[-1].content if messages else "No response."
    tools_used = _extract_tool_usage(messages)
    touched = _extract_touched_nodes(messages)

    # Cache for /graph endpoint
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
def get_graph(level: str = "conceptual", limit: int = 200) -> GraphResponse:
    """Return node/edge data for graph visualization.

    If the /ask endpoint was called recently, highlights nodes touched by
    the last answer. Otherwise returns a level-filtered slice of the graph.
    """
    _, driver = _ensure_agent()

    with driver.session() as session:
        # Get nodes
        node_result = session.run(
            """
            MATCH (n {level: $level})
            WITH n LIMIT $limit
            RETURN elementId(n) AS id,
                   labels(n) AS labels,
                   n.tag AS tag,
                   n.name AS name,
                   properties(n) AS props
            """,
            level=level,
            limit=limit,
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


@app.get("/health")
def health() -> dict:
    """Health check."""
    return {"status": "ok", "model": "chatpid-api"}
