"""Semantic enrichment tests with a fake LLM and a recording fake driver.

No LLM calls, no network, no Neo4j, no real sleeping.
"""

from __future__ import annotations

import pytest

from chatpid import semantic_enrichment as se
from tests.fakes import FakeDriver, FakeLLM

# --- fake graph data ------------------------------------------------------------------------------

NODE_ROWS = [
    {
        "eid": "e1",
        "tag": "T4750",
        "labels": ["Node", "Tank"],
        "props": {
            "level": "conceptual",
            "element_id": "x1",
            "tag": "T4750",
            "volume": 10,
        },
    },
    {
        "eid": "e2",
        "tag": None,
        "labels": ["Node", "Pump"],
        "props": {"level": "conceptual", "element_id": "x2"},
    },
]


def _responder(query: str, params: dict) -> list[dict]:
    if "RETURN elementId(n) AS eid" in query:
        return NODE_ROWS
    if "-[r {level: $level}]->" in query:
        return [
            {
                "neighbor_tag": "P4711",
                "neighbor_labels": ["Node", "Pump"],
                "rel_type": "FLOWS_TO",
            }
        ]
    if "<-[r {level: $level}]-" in query:
        return [
            {
                "neighbor_tag": "V1",
                "neighbor_labels": ["Node", "Valve", "Gate"],
                "rel_type": "CONNECTS",
            }
        ]
    return []


@pytest.fixture
def driver() -> FakeDriver:
    return FakeDriver(_responder)


@pytest.fixture
def llm(monkeypatch) -> FakeLLM:
    fake = FakeLLM(reply="  Moves liquid.  ")
    monkeypatch.setattr(se, "get_llm", lambda temperature=0, **kw: fake)
    monkeypatch.setattr(
        se, "context_rag", lambda drv, level, mode: f"TOPOLOGY[{level},{mode}]"
    )
    return fake


@pytest.fixture
def sleeps(monkeypatch) -> list[float]:
    recorded: list[float] = []
    monkeypatch.setattr(se.time, "sleep", recorded.append)
    return recorded


# --- data access helpers --------------------------------------------------------------------------


def test_get_all_nodes_strips_generic_label_and_internal_properties(driver):
    nodes = se._get_all_nodes(driver, "conceptual")

    assert nodes == [
        {
            "element_id": "e1",
            "tag": "T4750",
            "labels": ["Tank"],
            "properties": {"tag": "T4750", "volume": 10},
        },
        {"element_id": "e2", "tag": None, "labels": ["Pump"], "properties": {}},
    ]
    assert driver.calls[0][1] == {"level": "conceptual"}


def test_get_neighbors_text_formats_incoming_and_outgoing_connections(driver):
    incoming, outgoing = se._get_neighbors_text(driver, "T4750", "conceptual")

    assert outgoing == "  -> [P4711] (Pump) via FLOWS_TO"
    assert incoming == "  <- [V1] (Valve, Gate) via CONNECTS"
    assert all(p == {"tag": "T4750", "level": "conceptual"} for _, p in driver.calls)


def test_get_neighbors_text_says_none_when_there_are_no_neighbors():
    incoming, outgoing = se._get_neighbors_text(FakeDriver(), "T1", "conceptual")

    assert incoming == "  (none)"
    assert outgoing == "  (none)"


def test_write_semantics_sets_both_properties_on_the_node():
    driver = FakeDriver()

    se._write_semantics(driver, "e1", "global text", "local text")

    ((query, params),) = driver.calls
    assert "SET n.global_semantic = $global_sem" in query
    assert "n.local_semantic = $local_sem" in query
    assert params == {
        "eid": "e1",
        "global_sem": "global text",
        "local_sem": "local text",
    }


# --- enrich_all_nodes -----------------------------------------------------------------------------


def test_enrich_all_nodes_returns_stripped_semantics_and_writes_them_back(
    driver, llm, sleeps
):
    results = se.enrich_all_nodes(driver, level="conceptual", verbose=False)

    assert results == [
        se.NodeSemantics("e1", "T4750", "Moves liquid.", "Moves liquid."),
        se.NodeSemantics(
            "e2", "e2", "Moves liquid.", "Moves liquid."
        ),  # no tag: falls back to element id
    ]
    writes = driver.queries_containing("SET n.global_semantic")
    assert [p["eid"] for _, p in writes] == ["e1", "e2"]
    assert all(
        p["global_sem"] == "Moves liquid." and p["local_sem"] == "Moves liquid."
        for _, p in writes
    )
    assert sleeps == []  # delay defaults to 0


def test_enrich_all_nodes_calls_the_llm_twice_per_node_with_node_context(
    driver, llm, sleeps
):
    se.enrich_all_nodes(driver, level="conceptual", verbose=False)

    assert len(llm.prompts) == 4  # global + local for each of two nodes
    global_prompt, local_prompt = llm.prompts[0], llm.prompts[1]
    assert "Labels: ['Tank']" in global_prompt
    assert "'volume': 10" in global_prompt
    assert "TOPOLOGY[conceptual,topology]" in global_prompt
    assert "Central Node:" in local_prompt
    assert "  -> [P4711] (Pump) via FLOWS_TO" in local_prompt
    assert "  <- [V1] (Valve, Gate) via CONNECTS" in local_prompt


def test_enrich_all_nodes_caps_the_flowsheet_context_at_3000_chars(
    driver, monkeypatch, sleeps
):
    fake = FakeLLM()
    monkeypatch.setattr(se, "get_llm", lambda temperature=0, **kw: fake)
    monkeypatch.setattr(se, "context_rag", lambda drv, level, mode: "x" * 5000)

    se.enrich_all_nodes(driver, verbose=False)

    assert "x" * 3000 in fake.prompts[0]
    assert "x" * 3001 not in fake.prompts[0]


def test_enrich_all_nodes_records_an_error_and_keeps_going_when_the_llm_fails(
    driver, monkeypatch, sleeps
):
    failing = FakeLLM(fail_on="Tank")  # the first node's prompts mention Tank
    monkeypatch.setattr(se, "get_llm", lambda temperature=0, **kw: failing)
    monkeypatch.setattr(se, "context_rag", lambda drv, level, mode: "ctx")

    results = se.enrich_all_nodes(driver, verbose=False)

    assert results[0] == se.NodeSemantics("e1", "T4750", "", "ERROR: llm unavailable")
    assert results[1].global_semantic == "fake description"
    assert not results[1].local_semantic.startswith("ERROR")
    written = [p["eid"] for _, p in driver.queries_containing("SET n.global_semantic")]
    assert written == ["e2"]  # nothing written for the failed node


def test_enrich_all_nodes_sleeps_between_llm_calls_when_a_delay_is_set(
    driver, llm, sleeps
):
    se.enrich_all_nodes(driver, delay=0.5, verbose=False)

    assert (
        sleeps == [0.5] * 4
    )  # per node: after the global call and at the end of the node


def test_enrich_all_nodes_with_no_nodes_returns_an_empty_list(llm, sleeps):
    assert se.enrich_all_nodes(FakeDriver(), verbose=False) == []
    assert llm.prompts == []


def test_enrich_all_nodes_verbose_reports_progress_and_summary(
    driver, llm, sleeps, capsys
):
    se.enrich_all_nodes(driver, level="conceptual", verbose=True)

    out = capsys.readouterr().out
    assert "Enriching 2 nodes at level='conceptual'" in out
    assert "Done: 2/2 nodes enriched successfully" in out
