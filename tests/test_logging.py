"""Logging in the core modules (CPID-15): module loggers, tool/pipeline failures leave log records, the
level comes from CHATPID_LOG_LEVEL, and INFO output carries no questions, answers or secrets."""

from __future__ import annotations

import importlib
import logging

import pytest
from fastapi.testclient import TestClient
from langchain_core.messages import AIMessage, ToolMessage

from chatpid import agent, api, cypher_rag
from chatpid import logging_config as lc
from tests.fakes import FakeDriver

CORE_MODULES = [
    "agent",
    "api",
    "context_rag",
    "cypher_rag",
    "ingest",
    "llm",
    "path_rag",
    "semantic_enrichment",
    "vector_rag",
]


# --- AC1: module loggers and the level from the environment ---------------------------------------


@pytest.mark.parametrize("name", CORE_MODULES)
def test_core_module_has_a_module_logger(name):
    module = importlib.import_module(f"chatpid.{name}")
    assert isinstance(module.logger, logging.Logger)
    assert module.logger.name == f"chatpid.{name}"


@pytest.mark.parametrize(
    ("value", "expected"),
    [
        (None, logging.INFO),
        ("", logging.INFO),
        ("debug", logging.DEBUG),
        (" WARNING ", logging.WARNING),
        ("error", logging.ERROR),
        ("nonsense", logging.INFO),
    ],
)
def test_resolve_level_reads_names_and_defaults_to_info(value, expected):
    assert lc.resolve_level(value) == expected


@pytest.fixture
def clean_package_logger():
    package = logging.getLogger("chatpid")
    saved_handlers, saved_level = list(package.handlers), package.level
    for handler in list(package.handlers):
        package.removeHandler(handler)
    yield package
    for handler in list(package.handlers):
        package.removeHandler(handler)
    for handler in saved_handlers:
        package.addHandler(handler)
    package.setLevel(saved_level)


def test_configure_logging_uses_the_env_var_and_is_idempotent(
    monkeypatch, clean_package_logger
):
    monkeypatch.setenv(lc.LOG_LEVEL_ENV, "DEBUG")
    monkeypatch.setattr(logging.getLogger(), "handlers", [])

    assert lc.configure_logging() == logging.DEBUG
    assert lc.configure_logging() == logging.DEBUG

    assert clean_package_logger.level == logging.DEBUG
    assert (
        len(clean_package_logger.handlers) == 1
    )  # no duplicate handler on the second call


def test_configure_logging_defaults_to_info_without_the_env_var(
    monkeypatch, clean_package_logger
):
    monkeypatch.delenv(lc.LOG_LEVEL_ENV, raising=False)
    assert lc.configure_logging() == logging.INFO
    assert clean_package_logger.level == logging.INFO


def test_configure_logging_warns_and_falls_back_on_an_unknown_level(
    monkeypatch, clean_package_logger, caplog
):
    monkeypatch.setenv(lc.LOG_LEVEL_ENV, "loud")
    with caplog.at_level(logging.WARNING, logger="chatpid"):
        assert lc.configure_logging() == logging.INFO
    assert any("Unknown CHATPID_LOG_LEVEL" in r.getMessage() for r in caplog.records)


# --- AC2 / AC4: a tool failure is logged with its stack trace -------------------------------------


def test_safe_tool_logs_the_exception_with_a_stack_trace_and_still_returns_its_message(
    caplog,
):
    def boom():
        raise ValueError("bad cypher")

    with caplog.at_level(logging.INFO, logger="chatpid.agent"):
        result = agent._safe_tool("CypherRAG", boom)()

    assert result == "[CypherRAG error] ValueError: bad cypher"
    (record,) = [r for r in caplog.records if r.levelno >= logging.ERROR]
    assert record.name == "chatpid.agent"
    assert "CypherRAG" in record.getMessage()
    assert record.exc_info is not None
    assert (
        record.exc_info[0] is ValueError
    )  # the traceback is attached, not just the text


def test_a_successful_tool_call_logs_no_error(caplog):
    with caplog.at_level(logging.DEBUG, logger="chatpid.agent"):
        assert agent._safe_tool("Demo", lambda: "ok")() == "ok"
    assert [r for r in caplog.records if r.levelno >= logging.WARNING] == []


# --- AC3: swallowed exceptions in cypher_rag are logged at WARNING or above -----------------------


class _FailingDriver(FakeDriver):
    pass


def _pipeline(monkeypatch, execute, generated="MATCH (n) RETURN n"):
    monkeypatch.setattr(
        cypher_rag, "generate_cypher", lambda d, q, level="x": generated
    )
    monkeypatch.setattr(
        cypher_rag, "_retry_with_schema", lambda d, q, level, why: generated
    )
    monkeypatch.setattr(cypher_rag, "execute_cypher", execute)
    monkeypatch.setattr(cypher_rag, "context_rag", lambda d, level, mode: "ctx")
    monkeypatch.setattr(
        cypher_rag, "synthesize_answer", lambda q, c, r, context="": "a"
    )
    return cypher_rag.cypher_rag(FakeDriver(), "question text")


def test_cypher_rag_logs_both_swallowed_failures_before_falling_back(
    monkeypatch, caplog
):
    def boom(driver, cypher):
        raise RuntimeError("syntax error near MATCH")

    with caplog.at_level(logging.DEBUG, logger="chatpid.cypher_rag"):
        out = _pipeline(monkeypatch, boom)

    assert out["fallback"] is True
    warnings = [r for r in caplog.records if r.levelno >= logging.WARNING]
    assert (
        len(warnings) == 2
    )  # the first failure (retry) and the failed retry (fallback)
    assert all(r.name == "chatpid.cypher_rag" for r in warnings)
    assert warnings[1].exc_info is not None


def test_cypher_rag_logs_a_failed_retry_after_an_empty_result(monkeypatch, caplog):
    calls = {"n": 0}

    def empty_then_boom(driver, cypher):
        calls["n"] += 1
        if calls["n"] == 1:
            return []
        raise RuntimeError("retry exploded")

    with caplog.at_level(logging.DEBUG, logger="chatpid.cypher_rag"):
        out = _pipeline(monkeypatch, empty_then_boom)

    assert out["fallback"] is True
    assert [r for r in caplog.records if r.levelno >= logging.WARNING]


def test_cypher_rag_happy_path_logs_no_warning(monkeypatch, caplog):
    with caplog.at_level(logging.DEBUG, logger="chatpid.cypher_rag"):
        out = _pipeline(monkeypatch, lambda d, c: [{"tag": "T1"}])
    assert out["fallback"] is False
    assert [r for r in caplog.records if r.levelno >= logging.WARNING] == []


# --- API: events are logged without questions, answers or secrets at INFO -------------------------


class _Agent:
    def invoke(self, payload, config=None):
        return {
            "messages": [
                AIMessage(
                    content="",
                    tool_calls=[
                        {"name": "CypherRAG", "args": {"query": "q"}, "id": "1"}
                    ],
                ),
                ToolMessage(content="Tank T4750 at 42 bar", tool_call_id="1"),
                AIMessage(content="THE-SECRET-ANSWER"),
            ]
        }


@pytest.fixture
def client(monkeypatch):
    monkeypatch.setattr(api, "_driver", FakeDriver())
    monkeypatch.setattr(api, "_agent", _Agent())
    return TestClient(api.app, raise_server_exceptions=False)


def test_ask_logs_tool_names_and_timing_but_not_the_question_or_the_answer(
    client, caplog
):
    with caplog.at_level(logging.INFO, logger="chatpid"):
        response = client.post(
            "/ask", json={"question": "THE-SECRET-QUESTION about T4750"}
        )

    assert response.status_code == 200
    info_text = "\n".join(
        r.getMessage() for r in caplog.records if r.levelno >= logging.INFO
    )
    assert "CypherRAG" in info_text
    assert "THE-SECRET-QUESTION" not in info_text
    assert "THE-SECRET-ANSWER" not in info_text
    assert "42 bar" not in info_text


def test_parse_failure_on_ingest_is_logged_with_traceback_but_not_returned(
    client, monkeypatch, caplog
):
    def bad_loader(directory, filename):
        raise ValueError("cannot parse /tmp/xyz/upload.xml")

    monkeypatch.setattr(api, "load_dexpi_model", bad_loader)

    with caplog.at_level(logging.INFO, logger="chatpid"):
        response = client.post(
            "/ingest", files={"file": ("plant.xml", b"<x/>", "text/xml")}
        )

    assert response.status_code == 400
    assert "/tmp/xyz" not in response.text
    (record,) = [r for r in caplog.records if r.levelno >= logging.WARNING]
    assert record.name == "chatpid.api"
    assert record.exc_info is not None
