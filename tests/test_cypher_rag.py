"""Tests for CypherRAG. No Neo4j needed — uses mock driver."""

from __future__ import annotations

from unittest.mock import MagicMock

from chatpid.cypher_rag import execute_cypher, get_graph_schema


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


def test_get_graph_schema_returns_text():
    driver = MagicMock()
    session = driver.session.return_value.__enter__.return_value

    # Mock three sequential session.run calls: nodes, rels, tags
    session.run.side_effect = [
        # Node labels + properties
        [
            {"label": "Tank", "properties": ["tag", "level", "cylinderLength", "element_id"]},
            {"label": "Pump", "properties": ["tag", "level", "designPressureHead", "element_id"]},
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
