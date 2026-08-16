"""Smoke test for ContextRAG's text serialization, independent of Neo4j.

Uses a stub driver/session rather than a live database, since CI/local test
runs shouldn't require Neo4j to be up just to check the string formatting.
"""

from __future__ import annotations

from unittest.mock import MagicMock

from chatpid.context_rag import context_rag


def _fake_record(source_labels, source_tag, source_props, relationship, target_labels, target_tag):
    return {
        "source_labels": source_labels,
        "source_tag": source_tag,
        "source_props": source_props,
        "relationship": relationship,
        "target_labels": target_labels,
        "target_tag": target_tag,
    }


def test_context_rag_topology_mode_formats_edges():
    driver = MagicMock()
    session = driver.session.return_value.__enter__.return_value
    session.run.return_value = [
        _fake_record(["Node", "Pump"], "P1", {"level": "conceptual", "element_id": "1"}, "CONNECTED_TO", ["Node", "Tank"], "T1"),
    ]

    result = context_rag(driver, level="conceptual", mode="topology")

    assert result == "P1 --CONNECTED_TO--> T1"


def test_context_rag_rejects_unknown_level():
    driver = MagicMock()
    try:
        context_rag(driver, level="bogus")
    except ValueError as exc:
        assert "level" in str(exc)
    else:
        raise AssertionError("expected ValueError for invalid level")
