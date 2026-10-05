"""Regression tests for GET /pid/svg path containment (CPID-13).

No Neo4j or LLM needed: the DEXPI loader and renderer are replaced by fakes, so the tests prove which
(directory, filename) the endpoint hands to the loader and what the client is told.
"""

from __future__ import annotations

import os
from pathlib import Path
from typing import ClassVar

import pytest
from fastapi.testclient import TestClient

from chatpid import api

SECRET = "TOP-SECRET-CONTENT"


class FakeSerializer:
    """Records every load() call instead of parsing anything."""

    calls: ClassVar[list[tuple[str, str]]] = []

    def load(self, directory, filename):
        FakeSerializer.calls.append((str(directory), str(filename)))
        return type("Model", (), {"diagram": object()})()


class FakeDrawDiagram:
    def __init__(self, diagram, **kwargs):
        pass

    def draw_svg(self):
        return "<svg>fake</svg>"


@pytest.fixture
def pid_dirs(tmp_path, monkeypatch):
    """A cwd with data/dexpi_real/good.xml and data/raw/, plus a sibling dir whose files must stay unreachable."""
    for sub in ("data/dexpi_real", "data/raw", "outside"):
        (tmp_path / sub).mkdir(parents=True)
    (tmp_path / "data" / "dexpi_real" / "good.xml").write_text("<x/>")
    (tmp_path / "outside" / "secret.xml").write_text(SECRET)
    (tmp_path / "outside" / "secret.txt").write_text(SECRET)

    FakeSerializer.calls = []
    monkeypatch.setattr(api, "ProteusSerializer", FakeSerializer)
    monkeypatch.setattr(api, "DrawDiagram", FakeDrawDiagram)
    monkeypatch.chdir(
        tmp_path
    )  # the endpoint looks in cwd-relative data/dexpi_real and data/raw
    return tmp_path


@pytest.fixture
def client():
    return TestClient(api.app)


def _assert_rejected(response, tmp_path):
    assert 400 <= response.status_code < 500, response.text
    assert FakeSerializer.calls == []
    assert SECRET not in response.text
    assert str(tmp_path) not in response.text
    assert "data/dexpi_real" not in response.text
    assert "data\\dexpi_real" not in response.text


@pytest.mark.parametrize(
    "filename",
    [
        "../../outside/secret.xml",
        "..\\..\\outside\\secret.xml",
        "../raw/../../outside/secret.xml",
        "..",
        "good.xml/../../../outside/secret.xml",
        "",
        "secret.txt",
        "good.XML.txt",
    ],
)
def test_traversal_and_bad_names_are_rejected(client, pid_dirs, filename):
    response = client.get("/pid/svg", params={"filename": filename})
    _assert_rejected(response, pid_dirs)


def test_absolute_path_is_rejected(client, pid_dirs):
    absolute = str((pid_dirs / "outside" / "secret.xml").resolve())
    response = client.get("/pid/svg", params={"filename": absolute})
    _assert_rejected(response, pid_dirs)


@pytest.mark.parametrize(
    "raw_query",
    [
        "filename=..%2f..%2foutside%2fsecret.xml",
        "filename=%2e%2e%2f%2e%2e%2foutside%2fsecret.xml",
        "filename=..%5c..%5coutside%5csecret.xml",
        "filename=..%252f..%252foutside%252fsecret.xml",
        "filename=good.xml%00.txt",
    ],
)
def test_url_encoded_traversal_is_rejected(client, pid_dirs, raw_query):
    response = client.get(f"/pid/svg?{raw_query}")
    _assert_rejected(response, pid_dirs)


def test_symlink_pointing_outside_is_rejected(client, pid_dirs):
    link = pid_dirs / "data" / "dexpi_real" / "link.xml"
    try:
        os.symlink(pid_dirs / "outside" / "secret.xml", link)
    except (OSError, NotImplementedError) as exc:  # Windows without symlink privilege
        pytest.skip(f"cannot create symlinks here: {exc}")
    response = client.get("/pid/svg", params={"filename": "link.xml"})
    _assert_rejected(response, pid_dirs)


@pytest.mark.parametrize(
    "filename",
    [
        "../../outside/secret.xml",
        "../raw/../../outside/secret.xml",
        "..",
    ],
)
def test_find_pid_dir_never_touches_files_outside_the_base(
    pid_dirs, monkeypatch, filename
):
    """CPID-34/CPID-35 (CodeQL py/path-injection): the name is contained BEFORE any filesystem call.

    Checking containment after `is_file()` still stats a user-controlled path outside the allowed directory
    (an existence oracle, and the pattern CodeQL flags). The helper must reject the escape first, then probe.
    """
    probed: list[str] = []
    real_is_file = Path.is_file
    real_isfile = os.path.isfile

    def spy_is_file(self, *args, **kwargs):
        probed.append(os.path.realpath(self))
        return real_is_file(self, *args, **kwargs)

    def spy_isfile(path):
        probed.append(os.path.realpath(path))
        return real_isfile(path)

    monkeypatch.setattr(Path, "is_file", spy_is_file)
    monkeypatch.setattr(os.path, "isfile", spy_isfile)

    assert api._find_pid_dir(filename) is None

    allowed = [os.path.realpath(d) for d in api.PID_SEARCH_DIRS]
    for path in probed:
        assert any(path.startswith(base + os.sep) for base in allowed), (
            f"probed outside the base: {path}"
        )


def test_find_pid_dir_still_finds_legitimate_files(pid_dirs):
    assert api._find_pid_dir("good.xml") == "data/dexpi_real"
    assert api._find_pid_dir("nope.xml") is None


def test_valid_file_name_is_served(client, pid_dirs):
    response = client.get("/pid/svg", params={"filename": "good.xml"})
    assert response.status_code == 200
    assert response.headers["content-type"].startswith("image/svg+xml")
    assert response.text == "<svg>fake</svg>"
    assert len(FakeSerializer.calls) == 1
    directory, filename = FakeSerializer.calls[0]
    assert filename == "good.xml"
    assert Path(directory).resolve() == (pid_dirs / "data" / "dexpi_real").resolve()


def test_missing_file_is_404_without_paths(client, pid_dirs):
    response = client.get("/pid/svg", params={"filename": "nope.xml"})
    assert response.status_code == 404
    assert FakeSerializer.calls == []
    assert str(pid_dirs) not in response.text
    assert "data/dexpi_real" not in response.text


def test_render_failure_does_not_leak_exception_text(client, pid_dirs, monkeypatch):
    class Exploding:
        def load(self, directory, filename):
            raise RuntimeError(f"cannot open {directory}/{filename} at /secret/place")

    monkeypatch.setattr(api, "ProteusSerializer", Exploding)
    response = client.get("/pid/svg", params={"filename": "good.xml"})
    assert response.status_code == 500
    assert "/secret/place" not in response.text
    assert "good.xml" not in response.text


def test_real_reference_pid_renders(client, monkeypatch):
    """Unfaked end-to-end check on the tracked DEXPI sample: the fix must not break the happy path."""
    monkeypatch.chdir(Path(__file__).resolve().parent.parent)
    response = client.get("/pid/svg", params={"filename": "C03V04-VER.EX02.xml"})
    assert response.status_code == 200
    assert response.headers["content-type"].startswith("image/svg+xml")
    assert "<svg" in response.text
