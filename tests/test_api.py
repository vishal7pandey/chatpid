"""API tests: FastAPI TestClient with the agent, Neo4j driver, LLM and DEXPI loader replaced by fakes.

No Neo4j, no LLM, no network. /pid/svg has its own file (test_api_pid_svg.py).
"""

from __future__ import annotations

from types import SimpleNamespace
from typing import Any

import networkx as nx
import pytest
from fastapi.testclient import TestClient
from langchain_core.messages import AIMessage, HumanMessage, ToolMessage

from chatpid import api
from tests.fakes import FakeDriver

# --- fakes and fixtures ---------------------------------------------------------------------------


class FakeAgent:
    """Stands in for the LangGraph agent: returns canned messages and records how it was invoked."""

    def __init__(
        self, messages: list[Any] | None = None, error: Exception | None = None
    ):
        self.messages = (
            messages if messages is not None else [AIMessage(content="42 bar")]
        )
        self.error = error
        self.calls: list[tuple[dict, dict | None]] = []

    def invoke(self, payload: dict, config: dict | None = None) -> dict:
        self.calls.append((payload, config))
        if self.error:
            raise self.error
        return {"messages": self.messages}


@pytest.fixture
def driver() -> FakeDriver:
    return FakeDriver()


@pytest.fixture
def agent() -> FakeAgent:
    return FakeAgent()


@pytest.fixture
def client(monkeypatch, driver, agent):
    """TestClient whose app already holds the fake driver/agent, so nothing real is built."""
    monkeypatch.setattr(api, "_driver", driver)
    monkeypatch.setattr(api, "_agent", agent)
    # /ask writes these module globals; setattr first so monkeypatch restores them after the test
    monkeypatch.setattr(api, "_last_question", "")
    monkeypatch.setattr(api, "_last_answer", "")
    monkeypatch.setattr(api, "_last_tools", [])
    monkeypatch.setattr(api, "_last_graph_nodes", [])
    return TestClient(api.app, raise_server_exceptions=False)


# --- pure helpers ---------------------------------------------------------------------------------


def test_select_primary_label_prefers_most_specific_domain_label():
    labels = [
        "Node",
        "PipingComponent",
        "OperatedValve",
        "GlobeValve",
        "TaggedPlantItem",
    ]
    assert api._select_primary_label(labels) == "GlobeValve"


def test_select_primary_label_falls_back_to_first_then_node():
    assert api._select_primary_label(["Node", "Equipment"]) == "Node"
    assert api._select_primary_label([]) == "Node"


def test_extract_final_answer_takes_the_last_ai_message():
    messages = [
        HumanMessage(content="q"),
        AIMessage(content="first"),
        AIMessage(content="last"),
    ]
    assert api._extract_final_answer(messages) == "last"


def test_extract_final_answer_stringifies_non_string_content():
    messages = [AIMessage(content=["a", "b"])]
    assert api._extract_final_answer(messages) == "['a', 'b']"


def test_extract_final_answer_never_surfaces_raw_tool_output():
    messages = [
        HumanMessage(content="q"),
        ToolMessage(content="RAW CYPHER ROWS", tool_call_id="1"),
    ]
    answer = api._extract_final_answer(messages)
    assert "RAW CYPHER ROWS" not in answer
    assert answer.startswith("The agent did not produce a final answer")


def test_extract_tool_usage_lists_every_tool_call_in_order():
    messages = [
        AIMessage(
            content="",
            tool_calls=[
                {"name": "CypherRAG", "args": {"query": "list valves"}, "id": "1"},
                {"name": "PathRAG", "args": {"query": "trace"}, "id": "2"},
            ],
        ),
        ToolMessage(content="rows", tool_call_id="1"),
        AIMessage(content="done"),
    ]
    assert api._extract_tool_usage(messages) == [
        {"name": "CypherRAG", "args": {"query": "list valves"}},
        {"name": "PathRAG", "args": {"query": "trace"}},
    ]


def test_extract_touched_nodes_finds_tags_only_in_tool_messages():
    messages = [
        AIMessage(content="I mention T9999 but I am not a tool"),
        ToolMessage(
            content="Tank T4750 feeds pump P4711 via valve 66KL21 and SV 104.01; also C3",
            tool_call_id="1",
        ),
    ]
    assert sorted(api._extract_touched_nodes(messages)) == sorted(
        ["T4750", "P4711", "66KL21", "SV 104.01", "C3"]
    )


# --- /health and /pid/files -----------------------------------------------------------------------


def test_health(client):
    response = client.get("/health")
    assert response.status_code == 200
    assert response.json() == {"status": "ok", "model": "chatpid-api"}


def test_pid_files_lists_xml_once_per_name_from_both_dirs(
    client, tmp_path, monkeypatch
):
    (tmp_path / "data" / "dexpi_real").mkdir(parents=True)
    (tmp_path / "data" / "raw").mkdir(parents=True)
    (tmp_path / "data" / "dexpi_real" / "b.xml").write_text("<x/>")
    (tmp_path / "data" / "dexpi_real" / "a.xml").write_text("<x/>")
    (tmp_path / "data" / "dexpi_real" / "notes.txt").write_text("ignore me")
    (tmp_path / "data" / "raw" / "a.xml").write_text(
        "<x/>"
    )  # duplicate name, first dir wins
    (tmp_path / "data" / "raw" / "c.xml").write_text("<x/>")
    monkeypatch.chdir(tmp_path)

    response = client.get("/pid/files")

    assert response.status_code == 200
    assert response.json()["files"] == [
        {"filename": "a.xml", "directory": "data/dexpi_real"},
        {"filename": "b.xml", "directory": "data/dexpi_real"},
        {"filename": "c.xml", "directory": "data/raw"},
    ]


def test_pid_files_is_empty_when_no_data_dirs(client, tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    assert client.get("/pid/files").json() == {"files": []}


# --- /ask -----------------------------------------------------------------------------------------


def test_ask_returns_answer_tools_and_touched_nodes(client, agent):
    agent.messages = [
        HumanMessage(content="q"),
        AIMessage(
            content="",
            tool_calls=[{"name": "CypherRAG", "args": {"query": "q"}, "id": "1"}],
        ),
        ToolMessage(content="Tank T4750 design pressure 42 bar", tool_call_id="1"),
        AIMessage(content="T4750 is designed for 42 bar."),
    ]

    response = client.post(
        "/ask", json={"question": "What is the design pressure of T4750?"}
    )

    assert response.status_code == 200
    body = response.json()
    assert body["answer"] == "T4750 is designed for 42 bar."
    assert body["tools_used"] == [{"name": "CypherRAG", "args": {"query": "q"}}]
    assert body["graph_node_ids"] == ["T4750"]
    assert body["latency_seconds"] >= 0


def test_ask_prefixes_the_prompt_with_document_and_level_and_bounds_the_loop(
    client, agent
):
    client.post(
        "/ask",
        json={"question": "List valves", "level": "process", "document_id": "C01V04"},
    )

    ((payload, config),) = agent.calls
    assert payload == {
        "messages": [
            {
                "role": "user",
                "content": "[Target P&ID: C01V04] [Graph abstraction level: process] List valves",
            }
        ]
    }
    assert config == {"recursion_limit": 25}


def test_ask_defaults_to_conceptual_level_without_document(client, agent):
    client.post("/ask", json={"question": "List valves"})

    content = agent.calls[0][0]["messages"][0]["content"]
    assert content == "[Graph abstraction level: conceptual] List valves"


def test_ask_with_empty_level_and_document_sends_the_bare_question(client, agent):
    client.post("/ask", json={"question": "List valves", "level": ""})

    assert agent.calls[0][0]["messages"][0]["content"] == "List valves"


def test_ask_without_a_final_ai_message_returns_a_clear_error_answer(client, agent):
    agent.messages = [ToolMessage(content="boom", tool_call_id="1")]

    response = client.post("/ask", json={"question": "q"})

    assert response.status_code == 200
    assert response.json()["answer"].startswith(
        "The agent did not produce a final answer"
    )


def test_ask_rejects_a_request_without_a_question(client, agent):
    response = client.post("/ask", json={"level": "conceptual"})

    assert response.status_code == 422
    assert agent.calls == []


def test_ask_agent_failure_is_a_500_that_does_not_echo_the_exception(client, agent):
    agent.error = RuntimeError("neo4j password is hunter2")

    response = client.post("/ask", json={"question": "q"})

    assert response.status_code == 500
    assert "hunter2" not in response.text


def test_ensure_agent_builds_driver_and_agent_once(monkeypatch):
    built = {"driver": 0, "agent": 0}
    fake_driver, fake_agent = FakeDriver(), FakeAgent()

    def fake_get_driver():
        built["driver"] += 1
        return fake_driver

    def fake_build_agent(drv):
        built["agent"] += 1
        assert drv is fake_driver
        return fake_agent

    monkeypatch.setattr(api, "_driver", None)
    monkeypatch.setattr(api, "_agent", None)
    monkeypatch.setattr(api, "get_driver", fake_get_driver)
    monkeypatch.setattr(api, "build_agent", fake_build_agent)

    assert api._ensure_agent() == (fake_agent, fake_driver)
    assert api._ensure_agent() == (fake_agent, fake_driver)
    assert built == {"driver": 1, "agent": 1}


# --- /graph ---------------------------------------------------------------------------------------

VALVE_ID = "4:db:1"
TANK_ID = "4:db:2"


def _graph_responder(query: str, params: dict) -> list[dict]:
    if "RETURN elementId(a) AS source" in query:
        return [{"source": TANK_ID, "target": VALVE_ID, "type": "FLOWS_TO"}]
    return [
        {
            "id": VALVE_ID,
            "labels": ["Node", "PipingComponent", "GlobeValve"],
            "tag": "V1",
            "name": "Inlet valve",
            "props": {
                "level": "conceptual",
                "embedding": [0.1, 0.2],
                "tag": "V1",
                "size": 5,
            },
        },
        {
            "id": TANK_ID,
            "labels": ["Node", "Tank"],
            "tag": None,
            "name": None,
            "props": {"level": "conceptual", "volume": 10},
        },
    ]


def test_graph_returns_nodes_and_edges_without_internal_properties(client, driver):
    driver.responder = _graph_responder

    response = client.get("/graph", params={"level": "conceptual", "limit": 50})

    assert response.status_code == 200
    body = response.json()
    assert body["level"] == "conceptual"
    assert body["total_nodes"] == 2
    valve, tank = body["nodes"]
    assert valve == {
        "id": VALVE_ID,
        "label": "GlobeValve",
        "tags": ["V1"],
        "properties": {"name": "Inlet valve", "tag": "V1", "size": 5},
    }
    assert tank == {
        "id": TANK_ID,
        "label": "Tank",
        "tags": [],
        "properties": {"volume": 10},
    }
    assert body["edges"] == [
        {"source": TANK_ID, "target": VALVE_ID, "type": "FLOWS_TO"}
    ]


def test_graph_passes_level_limit_and_node_ids_to_the_queries(client, driver):
    driver.responder = _graph_responder

    client.get("/graph", params={"level": "process", "limit": 7})

    node_query, node_params = driver.calls[0]
    assert "document_id" not in node_query
    assert node_params["level"] == "process"
    assert node_params["limit"] == 7
    assert node_params["document_id"] is None
    _, edge_params = driver.calls[1]
    assert edge_params == {"ids": [VALVE_ID, TANK_ID]}


def test_graph_scopes_to_a_document_when_given(client, driver):
    driver.responder = _graph_responder

    client.get("/graph", params={"document_id": "doc42"})

    node_query, node_params = driver.calls[0]
    assert "document_id: $document_id" in node_query
    assert node_params["document_id"] == "doc42"
    assert node_params["level"] == "conceptual"


def test_graph_with_no_nodes_is_an_empty_graph(client, driver):
    response = client.get("/graph")

    assert response.status_code == 200
    assert response.json() == {
        "nodes": [],
        "edges": [],
        "level": "conceptual",
        "total_nodes": 0,
    }


def test_graph_rejects_a_non_integer_limit(client, driver):
    response = client.get("/graph", params={"limit": "lots"})

    assert response.status_code == 422
    assert driver.calls == []


# --- /ingest --------------------------------------------------------------------------------------


def _graphs() -> SimpleNamespace:
    def graph(n_nodes: int) -> nx.MultiDiGraph:
        g = nx.MultiDiGraph()
        g.add_nodes_from(range(n_nodes))
        if n_nodes > 1:
            g.add_edge(0, 1)
        return g

    return SimpleNamespace(complete=graph(3), process=graph(2), conceptual=graph(1))


@pytest.fixture
def ingest_fakes(monkeypatch):
    """Replace the DEXPI loader and Neo4j loader with recorders."""
    rec: dict[str, Any] = {
        "loaded": [],
        "graphs_loaded": [],
        "uploaded_bytes": None,
        "error": None,
    }

    def fake_load_dexpi_model(directory, filename):
        if rec["error"]:
            raise rec["error"]
        rec["loaded"].append((str(directory), filename))
        rec["uploaded_bytes"] = (api.Path(directory) / filename).read_bytes()
        return "model"

    def fake_load_graph(drv, graph, level, document_id="default"):
        rec["graphs_loaded"].append((drv, graph.number_of_nodes(), level, document_id))

    monkeypatch.setattr(api, "load_dexpi_model", fake_load_dexpi_model)
    monkeypatch.setattr(api, "build_graph_abstractions", lambda model: _graphs())
    monkeypatch.setattr(api, "load_graph", fake_load_graph)
    return rec


def test_ingest_loads_all_three_levels_under_one_new_document_id(
    client, driver, ingest_fakes
):
    response = client.post(
        "/ingest", files={"file": ("plant.xml", b"<Proteus/>", "text/xml")}
    )

    assert response.status_code == 200
    body = response.json()
    assert len(body["document_id"]) == 8
    assert body["levels"] == {
        "complete": {"nodes": 3, "edges": 1},
        "process": {"nodes": 2, "edges": 1},
        "conceptual": {"nodes": 1, "edges": 0},
    }
    # CPID-20: the client's filename is never used as a path; the upload is stored under a fixed name
    assert ingest_fakes["loaded"][0][1] == api.UPLOAD_TMP_NAME
    assert ingest_fakes["uploaded_bytes"] == b"<Proteus/>"
    assert ingest_fakes["graphs_loaded"] == [
        (driver, 3, "complete", body["document_id"]),
        (driver, 2, "process", body["document_id"]),
        (driver, 1, "conceptual", body["document_id"]),
    ]


def test_ingest_gives_each_upload_its_own_document_id(client, ingest_fakes):
    ids = {
        client.post(
            "/ingest", files={"file": ("plant.xml", b"<x/>", "text/xml")}
        ).json()["document_id"]
        for _ in range(3)
    }
    assert len(ids) == 3


def test_ingest_rejects_a_non_xml_upload_before_touching_anything(client, ingest_fakes):
    response = client.post(
        "/ingest", files={"file": ("plant.txt", b"hello", "text/plain")}
    )

    assert response.status_code == 400
    assert ".xml" in response.json()["detail"]
    assert ingest_fakes["loaded"] == []
    assert ingest_fakes["graphs_loaded"] == []


def test_ingest_requires_a_file(client, ingest_fakes):
    assert client.post("/ingest").status_code == 422


def test_ingest_reports_a_parse_failure_as_400_and_loads_nothing(client, ingest_fakes):
    ingest_fakes["error"] = ValueError("not a Proteus document")

    response = client.post(
        "/ingest", files={"file": ("bad.xml", b"garbage", "text/xml")}
    )

    assert response.status_code == 400
    assert response.json()["detail"].startswith("Failed to parse DEXPI file")
    assert ingest_fakes["graphs_loaded"] == []
