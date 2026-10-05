"""CypherRAG must run LLM-generated Cypher in a read transaction (CPID-12).

The regex in `_validate_read_only` is only a second layer: it is a blocklist and can be evaded. The
first layer is the database itself, reached by opening the session with READ_ACCESS and running the query
through `execute_read`. These tests use the recording fake driver, which can model a server that refuses
writes in read-only sessions/transactions. Proof against a real Neo4j is in test_cypher_rag_live.py (opt-in).
"""

from __future__ import annotations

import re

import pytest
from neo4j import READ_ACCESS
from neo4j.exceptions import ClientError

from chatpid import cypher_rag
from chatpid.cypher_rag import (
    _validate_read_only,
    execute_cypher,
    get_graph_schema,
)
from tests.fakes import FakeDriver

# What the fake "database" treats as a write: write clauses plus procedures that write or administer.
_DB_WRITES = re.compile(
    r"\b(CREATE|MERGE|SET|DELETE|REMOVE|DROP|STOP|START|ALTER|GRANT)\b"
    r"|\bCALL\s+(gds\.\w+\.write|custom\.writeproc)\b",
    re.IGNORECASE,
)


def _is_write(query: str) -> bool:
    return bool(_DB_WRITES.search(query))


def _rows(query: str, params: dict) -> list[dict]:
    return [{"tag": "T4750"}]


@pytest.fixture
def driver() -> FakeDriver:
    return FakeDriver(_rows, write_detector=_is_write)


# Statements that the regex blocklist lets through (documented gaps) but that write or administer.
REGEX_EVADING_WRITES = [
    "CALL gds.pageRank.write('g', {writeProperty: 'pr'})",
    "call   GDS.pageRank.WRITE ( 'g' )",
    "CALL custom.writeProc('x')",
    "STOP DATABASE neo4j",
    "ALTER USER neo4j",
    "GRANT ROLE admin TO bob",
]


# --- AC1: every generated query runs in a read transaction ------------------------------------------


def test_execute_cypher_opens_a_read_access_session_and_a_read_transaction(driver):
    result = execute_cypher(driver, "MATCH (n {tag: 'T4750'}) RETURN n.tag AS tag")

    assert result == [{"tag": "T4750"}]
    assert driver.session_configs == [{"default_access_mode": READ_ACCESS}]
    assert driver.read_transactions == 1
    assert driver.write_transactions == 0


def test_every_session_the_module_opens_is_read_only():
    driver = FakeDriver()  # empty graph: introspection queries return no rows
    get_graph_schema(driver, level="conceptual")
    cypher_rag._get_label_list(driver, level="conceptual")
    execute_cypher(driver, "MATCH (n) RETURN n.tag AS tag")

    assert driver.session_configs  # sessions really were opened
    assert all(
        cfg.get("default_access_mode") == READ_ACCESS for cfg in driver.session_configs
    )


def test_cypher_rag_pipeline_runs_the_generated_query_in_a_read_transaction(
    driver, monkeypatch
):
    monkeypatch.setattr(
        cypher_rag,
        "generate_cypher",
        lambda d, q, level="conceptual": "MATCH (n) RETURN n.tag AS tag",
    )
    monkeypatch.setattr(
        cypher_rag, "synthesize_answer", lambda q, c, r, context="": "T4750"
    )

    out = cypher_rag.cypher_rag(driver, "which tag?")

    assert out["results"] == [{"tag": "T4750"}]
    assert out["fallback"] is False
    assert driver.read_transactions == 1
    assert driver.write_transactions == 0


# --- AC2: a statement that evades the regex is still rejected at the driver layer -------------------


@pytest.mark.parametrize("query", REGEX_EVADING_WRITES)
def test_regex_gaps_are_real_so_the_database_layer_is_needed(query):
    # Documents why the read transaction matters: the regex alone lets these through.
    _validate_read_only(query)  # does not raise


@pytest.mark.parametrize("query", REGEX_EVADING_WRITES)
def test_write_that_evades_the_regex_is_rejected_by_the_read_only_database_layer(
    driver, query
):
    with pytest.raises(ClientError, match="read access mode"):
        execute_cypher(driver, query)

    assert driver.write_transactions == 0


def test_the_fake_would_have_let_the_write_through_in_a_default_write_session(driver):
    """Control: without READ_ACCESS the fake accepts the same statement, so the tests above prove the mode."""
    with driver.session() as session:  # default (write) mode
        assert session.run("CALL gds.pageRank.write('g')") == [{"tag": "T4750"}]


@pytest.mark.parametrize(
    "query",
    ["CREATE (n:Evil)", "MATCH (n) SET n.x = 1", "MATCH (n) DETACH DELETE n"],
)
def test_regex_still_rejects_obvious_writes_before_touching_the_database(driver, query):
    with pytest.raises(ValueError, match="Write operation"):
        execute_cypher(driver, query)

    assert driver.calls == []
    assert driver.session_configs == []


def test_database_layer_rejects_even_when_the_regex_layer_is_bypassed(
    driver, monkeypatch
):
    monkeypatch.setattr(cypher_rag, "_validate_read_only", lambda cypher: None)

    with pytest.raises(ClientError):
        execute_cypher(driver, "CREATE (n:Evil)")


def test_a_database_rejection_makes_cypher_rag_fall_back_instead_of_writing(
    driver, monkeypatch
):
    monkeypatch.setattr(
        cypher_rag,
        "generate_cypher",
        lambda d, q, level="conceptual": "STOP DATABASE neo4j",
    )
    monkeypatch.setattr(
        cypher_rag, "_retry_with_schema", lambda d, q, level, why: "STOP DATABASE neo4j"
    )
    monkeypatch.setattr(
        cypher_rag, "synthesize_answer", lambda q, c, r, context="": "fallback answer"
    )
    monkeypatch.setattr(cypher_rag, "context_rag", lambda d, level, mode: "graph text")

    out = cypher_rag.cypher_rag(driver, "stop it")

    assert out["fallback"] is True
    assert out["results"] == []
    assert driver.write_transactions == 0
