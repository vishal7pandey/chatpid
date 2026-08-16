"""Smoke test for ContextRAG's text serialization, independent of Neo4j.

Uses a stub driver/session rather than a live database, since CI/local test
runs shouldn't require Neo4j to be up just to check the string formatting.
"""

from __future__ import annotations

from unittest.mock import MagicMock

from chatpid.context_rag import context_rag


def test_context_rag_topology_mode_formats_nodes_and_edges():
    driver = MagicMock()
    session = driver.session.return_value.__enter__.return_value

    # Mock: first run returns nodes, second run returns edges
    session.run.side_effect = [
        # Nodes
        [
            {"tag": "P1", "labels": ["Node", "Pump"], "props": {"level": "conceptual", "element_id": "1"}},
        ],
        # Edges
        [
            {"source": "P1", "rel": "CONNECTED_TO", "target": "T1"},
        ],
    ]

    result = context_rag(driver, level="conceptual", mode="topology")

    assert "[P1]" in result
    assert "P1 --CONNECTED_TO--> T1" in result


def test_context_rag_rejects_unknown_level():
    driver = MagicMock()
    try:
        context_rag(driver, level="bogus")
    except ValueError as exc:
        assert "level" in str(exc)
    else:
        raise AssertionError("expected ValueError for invalid level")
