"""Ingest tests: DEXPI -> graphs -> Neo4j statements, checked against a recording fake driver.

No Neo4j and no network. One test runs pyDEXPI for real on the small tracked sample file.
"""

from __future__ import annotations

import json
from pathlib import Path
from types import SimpleNamespace

import networkx as nx
import pytest

from chatpid import ingest
from chatpid.config import get_settings
from tests.fakes import FakeDriver

REPO_ROOT = Path(__file__).resolve().parent.parent
SAMPLE_DIR = REPO_ROOT / "data" / "dexpi_real"
SAMPLE_FILE = "C03V04-VER.EX02.xml"


def _small_graph() -> nx.MultiDiGraph:
    g = nx.MultiDiGraph()
    g.add_node(
        "n1",
        labels="GlobeValve:PipingComponent",
        positionNumber="V1",
        tagName="TAG-V1",
        size=5,
    )
    g.add_node("n2", labels="Tank", tagName="T1", meta={"a": 1})
    g.add_node("n3", label="Orphan")  # no labels, no tag fields
    g.add_edge("n2", "n1", type="flows to", weight=2)
    return g


def _merge_calls(driver: FakeDriver) -> list[tuple[str, dict]]:
    return driver.queries_containing("MERGE (n:")


# --- helpers --------------------------------------------------------------------------------------


@pytest.mark.parametrize(
    ("raw", "expected"),
    [
        ("GlobeValve", "GlobeValve"),
        ("Pipe Fitting!", "PipeFitting"),
        ("Valve) DETACH DELETE n //", "ValveDETACHDELETEn"),
        ("", "Node"),
        (None, "Node"),
        ("!!!", "Node"),
    ],
)
def test_safe_label_keeps_only_alphanumerics_and_underscore(raw, expected):
    assert ingest._safe_label(raw) == expected


@pytest.mark.parametrize(
    ("raw", "expected"),
    [
        ("flows to", "FLOWS_TO"),
        ("hasPart", "HASPART"),
        ("a]->(x) DELETE r //", "A____X__DELETE_R"),
        ("", "RELATED_TO"),
        (None, "RELATED_TO"),
        ("---", "RELATED_TO"),
    ],
)
def test_safe_rel_type_is_an_uppercase_identifier(raw, expected):
    assert ingest._safe_rel_type(raw) == expected


def test_serialize_value_keeps_primitives_and_json_encodes_the_rest():
    assert ingest._serialize_value(5) == 5
    assert ingest._serialize_value("x") == "x"
    assert ingest._serialize_value(None) is None
    assert ingest._serialize_value(True) is True
    assert json.loads(ingest._serialize_value({"a": [1, 2]})) == {"a": [1, 2]}
    assert ingest._serialize_value(Path("a/b")) == json.dumps(str(Path("a/b")))


# --- clear_level ----------------------------------------------------------------------------------


def test_clear_level_deletes_only_that_level_and_document():
    driver = FakeDriver()

    ingest.clear_level(driver, "process", document_id="docA")

    ((query, params),) = driver.calls
    assert "DETACH DELETE" in query
    assert "level: $level" in query and "document_id: $document_id" in query
    assert params == {"level": "process", "document_id": "docA"}


def test_clear_level_defaults_to_the_default_document():
    driver = FakeDriver()
    ingest.clear_level(driver, "complete")
    assert driver.calls[0][1] == {"level": "complete", "document_id": "default"}


# --- load_graph -----------------------------------------------------------------------------------


def test_load_graph_clears_the_level_and_document_before_loading():
    driver = FakeDriver()

    ingest.load_graph(driver, _small_graph(), "conceptual", document_id="docA")

    first_query, first_params = driver.calls[0]
    assert "DETACH DELETE" in first_query
    assert first_params == {"level": "conceptual", "document_id": "docA"}
    assert all("DETACH DELETE" not in q for q, _ in driver.calls[1:])


def test_load_graph_tags_every_node_with_level_document_and_element_id():
    driver = FakeDriver()

    ingest.load_graph(driver, _small_graph(), "conceptual", document_id="docA")

    merges = _merge_calls(driver)
    assert len(merges) == 3
    for query, params in merges:
        assert "element_id: $element_id" in query
        assert params["level"] == "conceptual"
        assert params["document_id"] == "docA"
        assert params["props"]["level"] == "conceptual"
        assert params["props"]["document_id"] == "docA"
        assert params["props"]["element_id"] == params["element_id"]


def test_load_graph_defaults_to_document_id_default():
    driver = FakeDriver()
    ingest.load_graph(driver, _small_graph(), "conceptual")
    assert {p["document_id"] for _, p in _merge_calls(driver)} == {"default"}


def test_load_graph_builds_label_string_with_generic_node_label_first():
    driver = FakeDriver()

    ingest.load_graph(driver, _small_graph(), "conceptual")

    queries = [q for q, _ in _merge_calls(driver)]
    assert queries[0].startswith("MERGE (n:Node:GlobeValve:PipingComponent {")
    assert queries[1].startswith("MERGE (n:Node:Tank {")
    assert queries[2].startswith("MERGE (n:Node:Orphan {")


def test_load_graph_computes_tag_from_first_available_identifier():
    driver = FakeDriver()

    ingest.load_graph(driver, _small_graph(), "conceptual")

    tags = [p["props"]["tag"] for _, p in _merge_calls(driver)]
    # tagName beats positionNumber; node with no identifier falls back to its label
    assert tags == ["TAG-V1", "T1", "Orphan"]


def test_load_graph_serialises_non_primitive_properties_and_drops_labels_key():
    driver = FakeDriver()

    ingest.load_graph(driver, _small_graph(), "conceptual")

    _, tank_params = _merge_calls(driver)[1]
    assert "labels" not in tank_params["props"]
    assert json.loads(tank_params["props"]["meta"]) == {"a": 1}
    _, valve_params = _merge_calls(driver)[0]
    assert valve_params["props"]["size"] == 5


def test_load_graph_sanitises_hostile_labels_before_putting_them_in_cypher():
    g = nx.MultiDiGraph()
    g.add_node("x", labels="Valve) DETACH DELETE n //:Pump")
    driver = FakeDriver()

    ingest.load_graph(driver, g, "conceptual")

    ((query, _),) = _merge_calls(driver)
    assert query.startswith("MERGE (n:Node:ValveDETACHDELETEn:Pump {")
    assert "DETACH DELETE" not in query


def test_load_graph_merges_edges_with_sanitised_type_and_scoped_endpoints():
    driver = FakeDriver()

    ingest.load_graph(driver, _small_graph(), "conceptual", document_id="docA")

    ((query, params),) = driver.queries_containing("MERGE (a)-[r:")
    assert "MERGE (a)-[r:FLOWS_TO]->(b)" in query
    assert params["source"] == "n2" and params["target"] == "n1"
    assert params["level"] == "conceptual" and params["document_id"] == "docA"
    assert params["props"]["weight"] == 2
    assert params["props"]["document_id"] == "docA"


def test_load_graph_with_empty_graph_only_clears():
    driver = FakeDriver()

    ingest.load_graph(driver, nx.MultiDiGraph(), "conceptual")

    assert len(driver.calls) == 1
    assert "DETACH DELETE" in driver.calls[0][0]


# --- DEXPI loading wrappers -----------------------------------------------------------------------


def test_load_dexpi_model_passes_directory_as_string_and_filename(
    monkeypatch, tmp_path
):
    seen = []

    class FakeSerializer:
        def load(self, directory, filename):
            seen.append((directory, filename))
            return "the-model"

    monkeypatch.setattr(ingest, "ProteusSerializer", FakeSerializer)

    assert ingest.load_dexpi_model(tmp_path, "a.xml") == "the-model"
    assert seen == [(str(tmp_path), "a.xml")]


def test_build_graph_abstractions_builds_all_three_levels(monkeypatch):
    class FakeLoader:
        def parse_dexpi_to_graph(self, model):
            assert model == "m"
            return "plant-graph"

    class FakeAbstractor:
        @staticmethod
        def build_complete_graph(g):
            return ("complete", g)

        @staticmethod
        def build_process_graph(g):
            return ("process", g)

        @staticmethod
        def build_conceptual_graph(g):
            return ("conceptual", g)

    monkeypatch.setattr(ingest, "GraphLoader", FakeLoader)
    monkeypatch.setattr(ingest, "GraphAbstractor", FakeAbstractor)

    graphs = ingest.build_graph_abstractions("m")

    assert graphs == ingest.FlowsheetGraphs(
        complete=("complete", "plant-graph"),
        process=("process", "plant-graph"),
        conceptual=("conceptual", "plant-graph"),
    )


def test_get_driver_uses_the_configured_uri_and_credentials(monkeypatch):
    monkeypatch.setenv("NEO4J_URI", "bolt://example:7687")
    monkeypatch.setenv("NEO4J_USER", "alice")
    monkeypatch.setenv("NEO4J_PASSWORD", "s3cret")
    get_settings.cache_clear()
    captured = {}

    def fake_driver(uri, auth):
        captured["uri"], captured["auth"] = uri, auth
        return "driver"

    monkeypatch.setattr(ingest, "GraphDatabase", SimpleNamespace(driver=fake_driver))
    try:
        assert ingest.get_driver() == "driver"
    finally:
        get_settings.cache_clear()
    assert captured == {"uri": "bolt://example:7687", "auth": ("alice", "s3cret")}


# --- real pyDEXPI on the small tracked sample -----------------------------------------------------


def test_real_sample_loads_builds_three_levels_and_writes_scoped_statements():
    model = ingest.load_dexpi_model(SAMPLE_DIR, SAMPLE_FILE)
    graphs = ingest.build_graph_abstractions(model)

    assert graphs.complete.number_of_nodes() > graphs.process.number_of_nodes() > 0
    assert graphs.process.number_of_nodes() >= graphs.conceptual.number_of_nodes() > 0

    driver = FakeDriver()
    ingest.load_graph(driver, graphs.conceptual, "conceptual", document_id="C03")

    merges = _merge_calls(driver)
    assert len(merges) == graphs.conceptual.number_of_nodes()
    assert {p["document_id"] for _, p in merges} == {"C03"}
    assert all(p["props"]["tag"] for _, p in merges)
    assert (
        len(driver.queries_containing("MERGE (a)-[r:"))
        == graphs.conceptual.number_of_edges()
    )
