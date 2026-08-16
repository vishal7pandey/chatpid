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
