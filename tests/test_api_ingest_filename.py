"""Regression tests for POST /ingest upload-filename handling (CPID-20).

The client-supplied multipart filename must never decide where the upload is written. The DEXPI loader,
graph builder and Neo4j loader are replaced by fakes; the temp directory is moved under pytest's tmp_path
so a write that escapes it is visible as a file left outside the sandbox.
"""

from __future__ import annotations

import os
import tempfile
from pathlib import Path
from types import SimpleNamespace
from typing import Any

import networkx as nx
import pytest
from fastapi.testclient import TestClient

from chatpid import api
from tests.fakes import FakeDriver


@pytest.fixture
def sandbox(tmp_path, monkeypatch) -> Path:
    """Temp dirs created by the endpoint land in <tmp_path>/sandbox/tmp; everything else is 'outside'."""
    root = tmp_path / "sandbox"
    (root / "tmp").mkdir(parents=True)
    (tmp_path / "outside").mkdir()
    monkeypatch.setattr(tempfile, "tempdir", str(root / "tmp"))
    return root


@pytest.fixture
def seen(monkeypatch) -> dict[str, Any]:
    rec: dict[str, Any] = {"loads": [], "error": None, "graphs_loaded": 0}

    def fake_load_dexpi_model(directory, filename):
        if rec["error"]:
            raise rec["error"]
        path = Path(directory) / filename
        rec["loads"].append((str(directory), filename, path.read_bytes()))
        return "model"

    def fake_graphs(model):
        g = nx.MultiDiGraph()
        g.add_node(1)
        return SimpleNamespace(complete=g, process=g, conceptual=g)

    def fake_load_graph(drv, graph, level, document_id="default"):
        rec["graphs_loaded"] += 1

    monkeypatch.setattr(api, "load_dexpi_model", fake_load_dexpi_model)
    monkeypatch.setattr(api, "build_graph_abstractions", fake_graphs)
    monkeypatch.setattr(api, "load_graph", fake_load_graph)
    monkeypatch.setattr(api, "_driver", FakeDriver())
    monkeypatch.setattr(api, "_agent", object())
    return rec


@pytest.fixture
def client():
    return TestClient(api.app, raise_server_exceptions=False)


def _files_left_behind(tmp_path: Path) -> list[str]:
    """Every file under tmp_path. The per-request temp dir is already deleted, so any file is an escape."""
    return sorted(
        str(p.relative_to(tmp_path)) for p in tmp_path.rglob("*") if p.is_file()
    )


def _post(client, name: str, content: bytes = b"<Proteus/>"):
    return client.post("/ingest", files={"file": (name, content, "text/xml")})


def test_valid_xml_upload_still_ingests(client, sandbox, seen, tmp_path):
    response = _post(client, "plant.xml")

    assert response.status_code == 200
    assert seen["graphs_loaded"] == 3
    assert len(seen["loads"]) == 1
    directory, _, content = seen["loads"][0]
    assert content == b"<Proteus/>"
    # the upload lived inside the endpoint's own temp dir, and nothing is left behind
    assert Path(directory).parent == sandbox / "tmp"
    assert _files_left_behind(tmp_path) == []


def test_client_filename_never_reaches_the_file_system(client, sandbox, seen):
    assert _post(client, "my plant (v2) é.xml").status_code == 200
    _, loaded_name, _ = seen["loads"][0]
    assert loaded_name == api.UPLOAD_TMP_NAME


@pytest.mark.parametrize(
    "name",
    [
        "../x.xml",
        "..\\x.xml",
        "../../x.xml",
        "sub/x.xml",
        "sub\\x.xml",
        "..",
        "C:x.xml",
        "x.xml:stream",
        "a..b.xml",
    ],
)
def test_traversal_style_names_are_rejected_and_nothing_is_written(
    client, sandbox, seen, tmp_path, name
):
    response = _post(client, name)

    assert 400 <= response.status_code < 500, response.text
    assert seen["loads"] == []
    assert seen["graphs_loaded"] == 0
    assert _files_left_behind(tmp_path) == []


@pytest.mark.parametrize(
    ("name", "ok"),
    [
        ("plant.xml", True),
        ("PLANT.XML", True),
        ("my plant (v2).xml", True),
        ("x\x00.xml", False),
        ("x.xml\x00", False),
        ("../x.xml", False),
        ("a/b.xml", False),
        ("a\\b.xml", False),
        ("C:x.xml", False),
        ("/abs.xml", False),
        ("x.txt", False),
    ],
)
def test_plain_xml_name_helper(name, ok):
    # NUL cannot be sent through the test client (httpx turns it into the literal text %00), so the
    # helper is pinned directly.
    assert api._is_plain_xml_name(name) is ok


def test_absolute_path_name_is_rejected_and_nothing_is_written(
    client, sandbox, seen, tmp_path
):
    target = tmp_path / "outside" / "evil.xml"

    # as_posix(): python-multipart already reduces a Windows `C:\x\y.xml` name to its basename, but a
    # forward-slash absolute path (POSIX, or `C:/x/y.xml`) reaches the endpoint unchanged on every OS.
    response = _post(client, target.as_posix(), b"PWNED")

    assert 400 <= response.status_code < 500, response.text
    assert not target.exists()
    assert seen["loads"] == []
    assert _files_left_behind(tmp_path) == []


@pytest.mark.parametrize("name", [" ", "plant", "plant.txt", "plant.xml.txt"])
def test_non_xml_names_are_still_rejected(client, sandbox, seen, name):
    response = _post(client, name)
    assert response.status_code == 400
    assert seen["loads"] == []


def test_ticket_exploit_dotdot_name_writes_nothing_above_the_temp_dir(
    client, sandbox, seen, tmp_path
):
    """The exact exploit from the ticket: '../../x.xml' must not create x.xml above the temp dir."""
    _post(client, "../../x.xml", b"PWNED")
    assert not (tmp_path / "x.xml").exists()
    assert not (sandbox / "x.xml").exists()
    assert not (sandbox / "tmp" / "x.xml").exists()


# --- CPID-41: where can the upload bytes land? (Sonar pythonsecurity:S2083 at the write_bytes sink) ---------

HOSTILE_NAMES = [
    "../x.xml",
    "../../x.xml",
    "..\\..\\x.xml",
    "/etc/x.xml",
    "C:/Windows/x.xml",
    "C:\\Windows\\x.xml",
    "\\\\server\\share\\x.xml",
    "%2e%2e%2fx.xml",
    "..%2fx.xml",
    "..%5cx.xml",
    "%252e%252e%252fx.xml",
    "x.xml\x00.txt",
    "plant.xml",
]


@pytest.fixture
def write_targets(monkeypatch) -> list[Path]:
    """Record the target of every Path.write_bytes (the sink Sonar flags) while still performing it."""
    targets: list[Path] = []
    original = Path.write_bytes

    def spy(self, data):
        targets.append(self)
        return original(self, data)

    monkeypatch.setattr(Path, "write_bytes", spy)
    return targets


@pytest.mark.parametrize("name", HOSTILE_NAMES)
def test_upload_bytes_only_ever_land_in_the_fixed_file_of_the_endpoint_temp_dir(
    client, sandbox, seen, write_targets, tmp_path, name
):
    _post(client, name, b"PWNED")

    for target in write_targets:
        assert target.name == api.UPLOAD_TMP_NAME
        assert target.parent.parent == sandbox / "tmp"
        # realpath-contained in the endpoint's temp dir, the shape Sonar and CodeQL recognise
        base = os.path.realpath(target.parent)
        assert os.path.realpath(target).startswith(base + os.sep)
    assert len(write_targets) == len(seen["loads"])
    assert _files_left_behind(tmp_path) == []


@pytest.mark.parametrize(
    "content",
    [
        b"../../x.xml",
        b"/etc/passwd",
        b"C:\\Windows\\win.ini",
        b"\x00\x00../..\x00",
        b"<?xml version='1.0'?><!DOCTYPE a [<!ENTITY e SYSTEM 'file:///etc/passwd'>]><a>&e;</a>",
    ],
)
def test_hostile_upload_content_is_data_never_a_path(
    client, sandbox, seen, write_targets, tmp_path, content
):
    assert _post(client, "plant.xml", content).status_code == 200

    assert [t.name for t in write_targets] == [api.UPLOAD_TMP_NAME]
    assert seen["loads"][0][2] == content
    assert _files_left_behind(tmp_path) == []


@pytest.mark.parametrize(
    "bad_name", ["../escape.xml", "../../escape.xml", "sub/../../escape.xml"]
)
def test_write_is_contained_in_the_temp_dir_at_the_point_of_use(
    client, sandbox, seen, write_targets, tmp_path, monkeypatch, bad_name
):
    """Defence in depth: even if the fixed name were ever changed to something escaping, nothing is written."""
    monkeypatch.setattr(api, "UPLOAD_TMP_NAME", bad_name)

    response = _post(client, "plant.xml", b"PWNED")

    assert response.status_code == 500
    assert write_targets == []
    assert seen["loads"] == []
    assert seen["graphs_loaded"] == 0
    assert _files_left_behind(tmp_path) == []
    assert str(tmp_path) not in response.text


def test_parse_failure_body_does_not_leak_paths_or_exception_text(
    client, sandbox, seen
):
    seen["error"] = ValueError("cannot read /secret/place/upload.xml line 3")

    response = _post(client, "plant.xml")

    assert response.status_code == 400
    body = response.text
    assert "/secret/place" not in body
    assert "upload.xml" not in body
    assert "line 3" not in body
    assert seen["graphs_loaded"] == 0


def test_rejection_bodies_do_not_leak_paths(client, sandbox, seen, tmp_path):
    response = _post(client, "../../x.xml")
    assert str(tmp_path) not in response.text
    assert "sandbox" not in response.text
