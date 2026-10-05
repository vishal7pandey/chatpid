"""Regression tests for request-state isolation in the API (CPID-14).

`/ask` used to store the last question, answer, tool calls and touched nodes in module-level globals, so
state from one caller lived in the process for every other caller. The API must be stateless: everything a
client needs comes back in the `/ask` response, and `/graph` depends only on its own parameters.
"""

from __future__ import annotations

import copy
import threading
from concurrent.futures import ThreadPoolExecutor
from typing import Any

import pytest
from fastapi.testclient import TestClient
from langchain_core.messages import AIMessage, ToolMessage

from chatpid import api
from tests.fakes import FakeDriver

TAGS = {"alice": "T4750", "bob": "P4711"}


class EchoTagAgent:
    """Answers with a tag taken from the question; optionally waits so two requests overlap in time."""

    def __init__(self, barrier: threading.Barrier | None = None):
        self.barrier = barrier

    def invoke(self, payload: dict, config: dict | None = None) -> dict:
        question = payload["messages"][0]["content"]
        who = "alice" if "alice" in question else "bob"
        if self.barrier is not None:
            self.barrier.wait(
                timeout=10
            )  # both requests are now inside the agent at once
        tag = TAGS[who]
        return {
            "messages": [
                AIMessage(
                    content="",
                    tool_calls=[{"name": "CypherRAG", "args": {"q": who}, "id": "1"}],
                ),
                ToolMessage(content=f"Found {tag}", tool_call_id="1"),
                AIMessage(content=f"answer for {who}"),
            ]
        }


def _graph_responder(query: str, params: dict) -> list[dict[str, Any]]:
    if "RETURN elementId(n) AS id" in query:
        return [
            {
                "id": "4:x:1",
                "labels": ["Node", "Tank"],
                "tag": "T4750",
                "name": "Tank",
                "props": {"level": params["level"], "tag": "T4750"},
            }
        ]
    return []


@pytest.fixture
def driver() -> FakeDriver:
    return FakeDriver(_graph_responder)


@pytest.fixture
def wire(monkeypatch, driver):
    def _wire(agent) -> TestClient:
        monkeypatch.setattr(api, "_driver", driver)
        monkeypatch.setattr(api, "_agent", agent)
        return TestClient(api.app, raise_server_exceptions=False)

    return _wire


def _mutable_module_state() -> dict[str, Any]:
    """Deep copy of every module-level str/list/dict/set in api.py, minus the lazily built singletons."""
    return {
        name: copy.deepcopy(value)
        for name, value in vars(api).items()
        if isinstance(value, (str, list, dict, set)) and not name.startswith("__")
    }


def test_ask_leaves_no_per_request_state_in_the_api_module(wire):
    client = wire(EchoTagAgent())
    before = _mutable_module_state()

    response = client.post("/ask", json={"question": "alice: what is the pressure?"})

    assert response.status_code == 200
    assert _mutable_module_state() == before


def test_api_module_has_no_last_request_globals_or_lock():
    leftovers = [
        name for name in vars(api) if name.startswith("_last_") or name == "_state_lock"
    ]
    assert leftovers == []


def test_two_overlapping_asks_each_get_only_their_own_nodes(wire):
    client_agent = EchoTagAgent(barrier=threading.Barrier(2))
    wire(client_agent)

    def ask(who: str) -> dict:
        # one TestClient per thread; the barrier in the agent forces the two requests to overlap
        with TestClient(api.app) as c:
            return c.post("/ask", json={"question": f"{who}: pressure?"}).json()

    with ThreadPoolExecutor(max_workers=2) as pool:
        futures = {who: pool.submit(ask, who) for who in TAGS}
        results = {who: f.result(timeout=20) for who, f in futures.items()}

    for who, body in results.items():
        assert body["answer"] == f"answer for {who}"
        assert body["graph_node_ids"] == [TAGS[who]]
        assert body["tools_used"] == [{"name": "CypherRAG", "args": {"q": who}}]


def test_interleaved_ask_graph_sequences_do_not_see_each_others_nodes(wire, driver):
    client = wire(EchoTagAgent())
    baseline = client.get("/graph", params={"level": "conceptual"}).json()

    # alice asks, bob asks, then both fetch the graph: same answer for both, unaffected by either ask
    a = client.post("/ask", json={"question": "alice: pressure?"}).json()
    b = client.post("/ask", json={"question": "bob: pressure?"}).json()
    graph_after_a_and_b = client.get("/graph", params={"level": "conceptual"}).json()

    assert a["graph_node_ids"] == ["T4750"]
    assert b["graph_node_ids"] == ["P4711"]
    assert graph_after_a_and_b == baseline
    # nothing from either ask is injected into the graph payload
    assert "P4711" not in str(graph_after_a_and_b)
    assert not any(
        key in graph_after_a_and_b for key in ("highlighted", "graph_node_ids")
    )
