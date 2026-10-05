"""VectorRAG tests with a fake embedding function and a recording fake driver.

No network, no model download, no Neo4j.
"""

from __future__ import annotations

import sys
from types import SimpleNamespace

import pytest

from chatpid import vector_rag
from chatpid.config import get_settings
from tests.fakes import FakeDriver


class FakeEmbedder:
    """Deterministic embeddings: [length of text, 1.0]. Records every text it embeds."""

    def __init__(self, model_name: str | None = None):
        self.model_name = model_name
        self.texts: list[str] = []

    def embed_query(self, text: str) -> list[float]:
        self.texts.append(text)
        return [float(len(text)), 1.0]


@pytest.fixture
def embedder(monkeypatch) -> FakeEmbedder:
    fake = FakeEmbedder()
    monkeypatch.setattr(vector_rag, "_embedder", fake)
    return fake


# --- embedder loading -----------------------------------------------------------------------------


def test_embedder_is_built_lazily_once_from_the_configured_model(monkeypatch):
    built = []

    class Recording(FakeEmbedder):
        def __init__(self, model_name):
            super().__init__(model_name)
            built.append(model_name)

    monkeypatch.setenv("CHATPID_EMBEDDING_MODEL", "my/embedding-model")
    get_settings.cache_clear()
    monkeypatch.setitem(
        sys.modules,
        "langchain_huggingface",
        SimpleNamespace(HuggingFaceEmbeddings=Recording),
    )
    monkeypatch.setattr(vector_rag, "_embedder", None)
    try:
        assert vector_rag.embed_text("hello") == [5.0, 1.0]
        assert vector_rag.embed_text("hello!") == [6.0, 1.0]
    finally:
        get_settings.cache_clear()

    assert built == ["my/embedding-model"]


def test_embed_text_uses_the_embedder(embedder):
    assert vector_rag.embed_text("pump") == [4.0, 1.0]
    assert embedder.texts == ["pump"]


# --- embed_and_store ------------------------------------------------------------------------------


def test_embed_and_store_writes_both_vectors_per_node_and_returns_the_count(embedder):
    def responder(query, params):
        if "RETURN elementId(n) AS eid" in query:
            return [
                {"eid": "e1", "global_sem": "gg", "local_sem": "l"},
                {"eid": "e2", "global_sem": "ggg", "local_sem": "ll"},
            ]
        return []

    driver = FakeDriver(responder)

    count = vector_rag.embed_and_store(driver, level="process")

    assert count == 2
    select_query, select_params = driver.calls[0]
    assert "IS NOT NULL" in select_query
    assert select_params == {"level": "process"}
    writes = driver.queries_containing("SET n.global_semantic_embedding")
    assert [p["eid"] for _, p in writes] == ["e1", "e2"]
    assert writes[0][1]["global_vec"] == [2.0, 1.0]
    assert writes[0][1]["local_vec"] == [1.0, 1.0]
    assert writes[1][1]["global_vec"] == [3.0, 1.0]
    assert embedder.texts == ["gg", "l", "ggg", "ll"]


def test_embed_and_store_with_no_enriched_nodes_writes_nothing(embedder):
    driver = FakeDriver()

    assert vector_rag.embed_and_store(driver) == 0
    assert len(driver.calls) == 1  # only the SELECT
    assert embedder.texts == []


# --- ensure_vector_indexes ------------------------------------------------------------------------


def test_ensure_vector_indexes_creates_global_and_local_cosine_indexes():
    driver = FakeDriver()

    vector_rag.ensure_vector_indexes(driver, dimensions=8)

    assert len(driver.calls) == 2
    (q1, p1), (q2, p2) = driver.calls
    assert "CREATE VECTOR INDEX global_semantic_index IF NOT EXISTS" in q1
    assert "n.global_semantic_embedding" in q1
    assert "CREATE VECTOR INDEX local_semantic_index IF NOT EXISTS" in q2
    assert "n.local_semantic_embedding" in q2
    assert p1 == p2 == {"dimensions": 8}
    assert "'cosine'" in q1 and "'cosine'" in q2


def test_ensure_vector_indexes_defaults_to_384_dimensions():
    driver = FakeDriver()
    vector_rag.ensure_vector_indexes(driver)
    assert driver.calls[0][1] == {"dimensions": 384}


# --- vector_rag -----------------------------------------------------------------------------------


def _hit(tag, labels, score, g="global", loc="local"):
    return {
        "tag": tag,
        "labels": labels,
        "global_semantic": g,
        "local_semantic": loc,
        "score": score,
    }


def test_vector_rag_queries_the_index_with_the_embedded_query(embedder):
    driver = FakeDriver()

    vector_rag.vector_rag(
        driver, "cool the tank", index="local_semantic_index", top_k=3, level="process"
    )

    ((query, params),) = driver.calls
    assert "db.index.vector.queryNodes" in query
    assert params == {
        "index": "local_semantic_index",
        "top_k": 3,
        "query_vector": [13.0, 1.0],
        "level": "process",
    }


def test_vector_rag_uses_default_index_top_k_and_level(embedder):
    driver = FakeDriver()
    vector_rag.vector_rag(driver, "q")
    params = driver.calls[0][1]
    assert (params["index"], params["top_k"], params["level"]) == (
        "global_semantic_index",
        5,
        "conceptual",
    )


def test_vector_rag_returns_tag_label_semantics_and_score(embedder):
    driver = FakeDriver(lambda q, p: [_hit("P4711", ["Node", "Pump"], 0.91)])

    results = vector_rag.vector_rag(driver, "pump")

    assert results == [
        {
            "tag": "P4711",
            "label": "Pump",
            "global_semantic": "global",
            "local_semantic": "local",
            "score": 0.91,
        }
    ]


def test_vector_rag_label_skips_the_generic_node_label(embedder):
    driver = FakeDriver(lambda q, p: [_hit("A", ["Node", "Tank", "Vessel"], 0.5)])
    assert vector_rag.vector_rag(driver, "q")[0]["label"] == "Tank"


@pytest.mark.parametrize("labels", [["Node"], [], None])
def test_vector_rag_label_is_empty_when_there_is_no_specific_label(embedder, labels):
    driver = FakeDriver(lambda q, p: [_hit("A", labels, 0.5)])
    assert vector_rag.vector_rag(driver, "q")[0]["label"] == ""


def test_vector_rag_with_no_hits_returns_an_empty_list(embedder):
    assert vector_rag.vector_rag(FakeDriver(), "q") == []


# --- vector_rag_text ------------------------------------------------------------------------------


def test_vector_rag_text_reports_no_hits(embedder):
    assert vector_rag.vector_rag_text(FakeDriver(), "q") == "No relevant nodes found."


def test_vector_rag_text_formats_hits_with_the_global_description_by_default(embedder):
    driver = FakeDriver(
        lambda q, p: [
            _hit("P4711", ["Node", "Pump"], 0.91234, g="Moves liquid", loc="Near T1")
        ]
    )

    text = vector_rag.vector_rag_text(driver, "pump")

    assert (
        text.splitlines()[0]
        == "VectorRAG results (top 1, index=global_semantic_index):"
    )
    assert "[1] P4711 (Pump) — score: 0.9123" in text
    assert "    Moves liquid" in text
    assert "Near T1" not in text


def test_vector_rag_text_uses_the_local_description_for_the_local_index(embedder):
    driver = FakeDriver(
        lambda q, p: [
            _hit("P4711", ["Node", "Pump"], 0.5, g="Moves liquid", loc="Near T1")
        ]
    )

    text = vector_rag.vector_rag_text(driver, "pump", index="local_semantic_index")

    assert "    Near T1" in text
    assert "Moves liquid" not in text


def test_vector_rag_text_truncates_long_descriptions_and_skips_empty_ones(embedder):
    rows = [
        _hit("A", ["Node", "Pump"], 0.9, g="x" * 500),
        _hit("B", ["Node", "Tank"], 0.8, g=""),
    ]
    driver = FakeDriver(lambda q, p: rows)

    text = vector_rag.vector_rag_text(driver, "q")

    assert "    " + "x" * 200 in text
    assert "x" * 201 not in text
    assert (
        text.splitlines()[-1] == "[2] B (Tank) — score: 0.8000"
    )  # no description line after the empty one
