"""Small hand-written fakes shared by the tests: a recording Neo4j driver and an LLM stand-in.

No network, no Neo4j. Each query the code under test sends is recorded in `driver.calls` as
`(query, params)` so tests can assert on what would have been executed.
"""

from __future__ import annotations

from collections.abc import Callable
from typing import Any, Self

from neo4j import READ_ACCESS
from neo4j.exceptions import ClientError

Responder = Callable[[str, dict[str, Any]], list[dict[str, Any]]]


def _no_rows(query: str, params: dict[str, Any]) -> list[dict[str, Any]]:
    return []


class FakeSession:
    def __init__(self, driver: FakeDriver, config: dict[str, Any] | None = None):
        self._driver = driver
        self.config = config or {}

    def __enter__(self) -> Self:
        return self

    def __exit__(self, *exc_info: object) -> bool:
        return False

    @property
    def read_only(self) -> bool:
        return self.config.get("default_access_mode") == READ_ACCESS

    def run(self, query: str, **params: Any) -> list[dict[str, Any]]:
        return self._run(query, params, read_only=self.read_only)

    def execute_read(self, fn: Callable[..., Any], *args: Any, **kwargs: Any) -> Any:
        self._driver.read_transactions += 1
        return fn(_Tx(self, read_only=True), *args, **kwargs)

    def execute_write(self, fn: Callable[..., Any], *args: Any, **kwargs: Any) -> Any:
        self._driver.write_transactions += 1
        return fn(_Tx(self, read_only=False), *args, **kwargs)

    def _run(
        self, query: str, params: dict[str, Any], read_only: bool
    ) -> list[dict[str, Any]]:
        self._driver.calls.append((query, params))
        detector = self._driver.write_detector
        if read_only and detector is not None and detector(query):
            # What a real server answers when a write is attempted in a read transaction
            raise ClientError("Writing in read access mode not allowed.")
        return self._driver.responder(query, params)


class _Tx:
    """Transaction handle that remembers whether it is read-only."""

    def __init__(self, session: FakeSession, read_only: bool):
        self._session = session
        self._read_only = read_only

    def run(self, query: str, **params: Any) -> list[dict[str, Any]]:
        return self._session._run(query, params, read_only=self._read_only)


class FakeDriver:
    """Records every `session.run(query, **params)` and answers via `responder(query, params)`.

    `session(**config)` records the session config (e.g. `default_access_mode`) in `session_configs`.
    If `write_detector(query) -> bool` is given, the fake behaves like a database that refuses writes in
    read-only sessions and read transactions (it raises `ClientError`), so tests can prove a statement is
    stopped at the driver layer even when the application-level guard lets it through. This models the
    server's behaviour; it does not replace a live-Neo4j check (tests/test_cypher_rag_live.py).
    """

    def __init__(
        self,
        responder: Responder = _no_rows,
        write_detector: Callable[[str], bool] | None = None,
    ):
        self.responder = responder
        self.write_detector = write_detector
        self.calls: list[tuple[str, dict[str, Any]]] = []
        self.session_configs: list[dict[str, Any]] = []
        self.read_transactions = 0
        self.write_transactions = 0
        self.closed = False

    def session(self, **config: Any) -> FakeSession:
        self.session_configs.append(config)
        return FakeSession(self, config)

    def close(self) -> None:
        self.closed = True

    def queries_containing(self, text: str) -> list[tuple[str, dict[str, Any]]]:
        return [(q, p) for q, p in self.calls if text in q]


class FakeResponse:
    """Mimics a LangChain message: only `.content` is read by the code under test."""

    def __init__(self, content: str):
        self.content = content


class FakeLLM:
    """`invoke(prompt)` returns canned text and records prompts; `fail_on` makes matching prompts raise."""

    def __init__(self, reply: str = "  fake description  ", fail_on: str | None = None):
        self.reply = reply
        self.fail_on = fail_on
        self.prompts: list[str] = []

    def invoke(self, prompt: str) -> FakeResponse:
        self.prompts.append(prompt)
        if self.fail_on and self.fail_on in prompt:
            raise RuntimeError("llm unavailable")
        return FakeResponse(self.reply)
