"""Tests for CypherRAG. No Neo4j needed — uses mock driver."""

from __future__ import annotations

from unittest.mock import MagicMock

import pytest

from chatpid.cypher_rag import _validate_read_only, execute_cypher, get_graph_schema
from tests.fakes import FakeDriver


def test_execute_cypher_rejects_create():
    driver = MagicMock()
    try:
        execute_cypher(driver, "CREATE (n:Test {tag: 'evil'})")
    except ValueError as exc:
        assert "CREATE" in str(exc)
    else:
        raise AssertionError("expected ValueError for CREATE")


def test_execute_cypher_rejects_delete():
    driver = MagicMock()
    try:
        execute_cypher(driver, "MATCH (n) DELETE n")
    except ValueError as exc:
        assert "DELETE" in str(exc)
    else:
        raise AssertionError("expected ValueError for DELETE")


def test_execute_cypher_rejects_merge():
    driver = MagicMock()
    try:
        execute_cypher(driver, "MERGE (n:Test {tag: 'evil'})")
    except ValueError as exc:
        assert "MERGE" in str(exc)
    else:
        raise AssertionError("expected ValueError for MERGE")


# --- Cypher injection regression test suite ---


class TestCypherInjectionRejection:
    """Regression tests for the write-guard fix.

    Each test asserts that a specific write operation or bypass attempt
    is rejected by _validate_read_only(). These codify the manual
    verification that was done during that fix but never committed.
    """

    @pytest.mark.parametrize(
        "query",
        [
            "MATCH (n) SET n.tag = 'evil'",
            "MATCH (n) SET n += {tag: 'evil'}",
            "MATCH (n {tag: 'T4750'}) SET n.cylinderLength = 999",
        ],
    )
    def test_rejects_set(self, query):
        with pytest.raises(ValueError, match="Write operation"):
            _validate_read_only(query)

    @pytest.mark.parametrize(
        "query",
        [
            "MATCH (n) FOREACH (x IN [1,2,3] | SET n.x = x)",
            "FOREACH (x IN [1,2] | CREATE (n:Test {val: x}))",
        ],
    )
    def test_rejects_foreach(self, query):
        with pytest.raises(ValueError, match="Write operation"):
            _validate_read_only(query)

    @pytest.mark.parametrize(
        "query",
        [
            "LOAD CSV WITH HEADERS FROM 'file:///evil.csv' AS row CREATE (n:Test {val: row.val})",
            "LOAD CSV FROM 'file:///evil.csv' AS row SET n.val = row.val",
        ],
    )
    def test_rejects_load_csv(self, query):
        with pytest.raises(ValueError, match="Write operation"):
            _validate_read_only(query)

    @pytest.mark.parametrize(
        "query",
        [
            "MATCH (n {tag: 'T4750'}) SET n.tag += 'evil'",
            "MATCH (n) SET n.val += 1",
        ],
    )
    def test_rejects_plus_equals(self, query):
        with pytest.raises(ValueError, match="Write operation"):
            _validate_read_only(query)

    @pytest.mark.parametrize(
        "query",
        [
            "MATCH (n) REMOVE n.tag",
            "MATCH (n) DETACH DELETE n",
            "MATCH (n) DROP n",
        ],
    )
    def test_rejects_remove_detach_delete_drop(self, query):
        with pytest.raises(ValueError, match="Write operation"):
            _validate_read_only(query)

    @pytest.mark.parametrize(
        "query",
        [
            "MATCH (n) sEt n.tag = 'evil'",
            "MATCH (n) SeT n.tag = 'evil'",
            "MATCH (n)  SET  n.tag = 'evil'",
            "MATCH (n)\nSET n.tag = 'evil'",
            "MATCH (n)\tSET\tn.tag = 'evil'",
        ],
    )
    def test_rejects_case_and_whitespace_variants(self, query):
        with pytest.raises(ValueError, match="Write operation"):
            _validate_read_only(query)

    @pytest.mark.parametrize(
        "query",
        [
            "CALL apoc.create.setProperty(n, 'tag', 'evil')",
            "CALL db.labels()",
            "CALL db.index.vector.queryNodes('idx', 5, [0.1, 0.2]) YIELD node RETURN node",
        ],
    )
    def test_rejects_call_db_and_apoc(self, query):
        with pytest.raises(ValueError, match="Write operation"):
            _validate_read_only(query)


class TestCypherInjectionLegitimateQueries:
    """Guard against overzealous matching — legitimate queries with
    set-like substrings must NOT be rejected."""

    @pytest.mark.parametrize(
        "query",
        [
            "MATCH (n {tag: 'T4750'}) RETURN n.cylinderLength AS offset",
            "MATCH (n {tag: 'T4750'}) RETURN n.offset",
            "MATCH (n {tag: 'T4750'}) RETURN n.reset",
            "MATCH (n) WHERE n.tag STARTS WITH 'T' RETURN n",
            "MATCH (n) RETURN n.tag, n.offset, n.reset ORDER BY n.offset",
        ],
    )
    def test_legitimate_queries_not_rejected(self, query):
        # Should NOT raise
        _validate_read_only(query)

    def test_legitimate_match_return_passes(self):
        """A simple MATCH/RETURN query must execute without error."""
        # CPID-12: the query now runs through session.execute_read, which a MagicMock cannot emulate,
        # so the recording fake driver stands in for Neo4j here. The assertion is unchanged.
        driver = FakeDriver(lambda query, params: [{"tag": "T4750"}])
        result = execute_cypher(driver, "MATCH (n {tag: 'T4750'}) RETURN n.tag AS tag")
        assert result == [{"tag": "T4750"}]


def test_get_graph_schema_returns_text():
    driver = MagicMock()
    session = driver.session.return_value.__enter__.return_value

    # Mock three sequential session.run calls: nodes, rels, tags
    session.run.side_effect = [
        # Node labels + properties
        [
            {
                "label": "Tank",
                "properties": ["tag", "level", "cylinderLength", "element_id"],
            },
            {
                "label": "Pump",
                "properties": ["tag", "level", "designPressureHead", "element_id"],
            },
        ],
        # Relationship types
        [
            {"relType": "PIPE", "properties": ["level", "fluidCode"]},
        ],
        # Sample tags
        [
            {"labels": ["Node", "Tank"], "sampleTags": ["T4750"]},
        ],
    ]

    schema = get_graph_schema(driver, level="conceptual")
    assert "Tank" in schema
    assert "Pump" in schema
    assert "PIPE" in schema
    assert "T4750" in schema
    assert "conceptual" in schema
