"""Tests for PathRAG path traversal logic. No Neo4j needed — uses mock driver."""

from __future__ import annotations

from unittest.mock import MagicMock

from chatpid.path_rag import (
    PathResult,
    _text_similarity,
    _tokenize,
    find_starting_nodes,
    path_rag,
)


def test_tokenize_handles_hyphens_and_underscores():
    tokens = _tokenize("heat-exchanger T4750 pump_P4711")
    assert "heat" in tokens
    assert "exchanger" in tokens
    assert "t4750" in tokens
    assert "pump" in tokens
    assert "p4711" in tokens


def test_text_similarity_returns_zero_for_no_overlap():
    score = _text_similarity({"tank", "t4750"}, "pump p4711")
    assert score == 0.0


def test_text_similarity_returns_high_for_exact_match():
    score = _text_similarity({"tank", "t4750"}, "tank T4750")
    assert score > 0.4


def test_find_starting_nodes_returns_top_k_by_score():
    driver = MagicMock()
    session = driver.session.return_value.__enter__.return_value
    session.run.return_value = [
        {"tag": "T4750", "labels": ["Node", "Tank"], "props": {"level": "conceptual", "label": "Tank"}},
        {"tag": "P4711", "labels": ["Node", "Pump"], "props": {"level": "conceptual", "label": "Pump"}},
        {"tag": "C1", "labels": ["Node", "Valve"], "props": {"level": "conceptual", "label": "Valve"}},
    ]

    results = find_starting_nodes(driver, "tank T4750", level="conceptual", max_breadth=2)
    assert len(results) == 2
    assert results[0]["tag"] == "T4750"  # highest score for "tank T4750"
    assert results[0]["_score"] > results[1]["_score"]


def test_path_rag_returns_empty_when_no_nodes():
    driver = MagicMock()
    session = driver.session.return_value.__enter__.return_value
    session.run.return_value = []

    result = path_rag(driver, "nonexistent query", level="conceptual")
    assert result.paths == []
    assert result.best_path is None


def test_path_rag_prefers_flow_direction():
    """A->B->C via outgoing edges, D->B via incoming edge.

    PathRAG starting at A should follow A->B->C (outgoing) rather than
    going A->B->D (against flow direction). The direction bonus ensures
    outgoing hops are preferred over incoming hops.
    """
    driver = MagicMock()
    session = driver.session.return_value.__enter__.return_value

    # find_starting_nodes: return node A
    # get_neighbors for A: return B (outgoing)
    # get_neighbors for B: return C (outgoing) and D (incoming)
    def mock_run(cypher, **kwargs):
        tag = kwargs.get("tag", "")
        if "UNWIND" not in cypher and "labels(n)" in cypher:
            # find_starting_nodes query
            return [
                {"tag": "A", "labels": ["Node", "Tank"], "props": {"level": "conceptual", "label": "Tank"}},
                {"tag": "B", "labels": ["Node", "Pump"], "props": {"level": "conceptual", "label": "Pump"}},
            ]
        if tag == "A":
            return [
                {"tag": "B", "labels": ["Node", "Pump"], "props": {"level": "conceptual", "label": "Pump"},
                 "rel_type": "PIPE", "direction": "out"},
            ]
        if tag == "B":
            return [
                {"tag": "C", "labels": ["Node", "Valve"], "props": {"level": "conceptual", "label": "Valve"},
                 "rel_type": "PIPE", "direction": "out"},
                {"tag": "D", "labels": ["Node", "Heater"], "props": {"level": "conceptual", "label": "Heater"},
                 "rel_type": "PIPE", "direction": "in"},
            ]
        return []

    session.run.side_effect = mock_run

    result = path_rag(driver, "tank A", level="conceptual", max_depth=3, max_breadth=1)
    assert len(result.paths) >= 1
    path = result.paths[0]
    # The path should go A -> B -> C (following flow direction)
    # NOT A -> B -> D (against flow direction)
    assert "C" in path.path
    # D should not be in the path (it's incoming direction, lower score)
    if "D" in path.path:
        # If D is in the path, C must come first (C has higher score due to direction bonus)
        assert path.path.index("C") < path.path.index("D")
