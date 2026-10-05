"""Agent tests: tool wrapping and wiring, with the LLM and the LangGraph builder replaced by fakes.

No LLM, no Neo4j, no network.
"""

from __future__ import annotations

import pytest

from chatpid import agent
from tests.fakes import FakeDriver

# --- _safe_tool -----------------------------------------------------------------------------------


def test_safe_tool_passes_results_and_arguments_through():
    wrapped = agent._safe_tool("Demo", lambda a, b=2: a + b)
    assert wrapped(1, b=5) == 6


def test_safe_tool_turns_an_exception_into_an_error_string_naming_the_tool():
    def boom():
        raise ValueError("bad cypher")

    result = agent._safe_tool("CypherRAG", boom)()

    assert result == "[CypherRAG error] ValueError: bad cypher"


def test_safe_tool_truncates_long_error_messages_to_300_chars():
    def boom():
        raise RuntimeError("x" * 1000)

    result = agent._safe_tool("PathRAG", boom)()

    assert result.startswith("[PathRAG error] RuntimeError: ")
    assert result.count("x") == 300


def test_safe_tool_does_not_swallow_keyboard_interrupt():
    def interrupted():
        raise KeyboardInterrupt

    with pytest.raises(KeyboardInterrupt):
        agent._safe_tool("Demo", interrupted)()


def test_safe_tool_keeps_the_wrapped_function_name():
    def my_tool():
        return "ok"

    assert agent._safe_tool("Demo", my_tool).__name__ == "my_tool"


# --- build_agent ----------------------------------------------------------------------------------


@pytest.fixture
def built(monkeypatch):
    """Run build_agent with the LLM and create_react_agent replaced; return what it was built from."""
    captured = {}
    fake_llm = object()

    def fake_get_llm(temperature=0, **kwargs):
        captured["temperature"] = temperature
        return fake_llm

    def fake_create_react_agent(llm, tools, prompt):
        captured.update(
            llm=llm,
            tools={t.name: t for t in tools},
            prompt=prompt,
            order=[t.name for t in tools],
        )
        return "the-agent"

    monkeypatch.setattr(agent, "get_llm", fake_get_llm)
    monkeypatch.setattr(agent, "create_react_agent", fake_create_react_agent)
    driver = FakeDriver()
    captured["result"] = agent.build_agent(driver)
    captured["driver"] = driver
    captured["fake_llm"] = fake_llm
    return captured


def test_build_agent_wires_the_four_graphrag_tools_and_the_system_prompt(built):
    assert built["result"] == "the-agent"
    assert built["order"] == ["ContextRAG", "VectorRAG", "PathRAG", "CypherRAG"]
    assert built["prompt"] == agent.SYSTEM_PROMPT
    assert built["llm"] is built["fake_llm"]
    assert built["temperature"] == 0


def test_system_prompt_names_every_tool_it_offers(built):
    for name in built["tools"]:
        assert name in agent.SYSTEM_PROMPT


def test_context_tool_delegates_with_the_driver_and_arguments(built, monkeypatch):
    calls = []
    monkeypatch.setattr(
        agent,
        "context_rag",
        lambda drv, level, mode: calls.append((drv, level, mode)) or "ctx",
    )

    result = built["tools"]["ContextRAG"].invoke(
        {"level": "process", "mode": "topology"}
    )

    assert result == "ctx"
    assert calls == [(built["driver"], "process", "topology")]


def test_context_tool_defaults_to_conceptual_graph_mode(built, monkeypatch):
    calls = []
    monkeypatch.setattr(
        agent,
        "context_rag",
        lambda drv, level, mode: calls.append((level, mode)) or "ctx",
    )

    built["tools"]["ContextRAG"].invoke({})

    assert calls == [("conceptual", "graph")]


def test_path_tool_delegates_with_depth_and_breadth(built, monkeypatch):
    calls = []

    def fake(drv, query, level, max_depth, max_breadth):
        calls.append((drv, query, level, max_depth, max_breadth))
        return "paths"

    monkeypatch.setattr(agent, "path_rag_text", fake)

    result = built["tools"]["PathRAG"].invoke(
        {"query": "trace T1 to P1", "max_depth": 4}
    )

    assert result == "paths"
    assert calls == [(built["driver"], "trace T1 to P1", "conceptual", 4, 2)]


def test_cypher_tool_delegates_query_and_level(built, monkeypatch):
    calls = []
    monkeypatch.setattr(
        agent,
        "cypher_rag_text",
        lambda drv, q, level: calls.append((drv, q, level)) or "rows",
    )

    result = built["tools"]["CypherRAG"].invoke(
        {"query": "list valves", "level": "process"}
    )

    assert result == "rows"
    assert calls == [(built["driver"], "list valves", "process")]


def test_vector_tool_delegates_with_index_and_top_k(built, monkeypatch):
    calls = []

    def fake(drv, query, index, top_k, level):
        calls.append((drv, query, index, top_k, level))
        return "hits"

    monkeypatch.setattr(agent, "vector_rag_text", fake)

    result = built["tools"]["VectorRAG"].invoke(
        {"query": "find pumps", "index": "local_semantic_index", "top_k": 3}
    )

    assert result == "hits"
    assert calls == [
        (built["driver"], "find pumps", "local_semantic_index", 3, "conceptual")
    ]


@pytest.mark.parametrize(
    ("tool_name", "target", "args"),
    [
        ("ContextRAG", "context_rag", {}),
        ("PathRAG", "path_rag_text", {"query": "q"}),
        ("CypherRAG", "cypher_rag_text", {"query": "q"}),
        ("VectorRAG", "vector_rag_text", {"query": "q"}),
    ],
)
def test_every_tool_returns_an_error_string_instead_of_crashing_the_agent(
    built, monkeypatch, tool_name, target, args
):
    def explode(*a, **k):
        raise ConnectionError("neo4j is down")

    monkeypatch.setattr(agent, target, explode)

    result = built["tools"][tool_name].invoke(args)

    assert result == f"[{tool_name} error] ConnectionError: neo4j is down"
