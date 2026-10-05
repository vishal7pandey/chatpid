"""Small hand-written fakes shared by the tests: a recording Neo4j driver and an LLM stand-in.

No network, no Neo4j. Each query the code under test sends is recorded in `driver.calls` as
`(query, params)` so tests can assert on what would have been executed.
"""

from __future__ import annotations

from collections.abc import Callable
from typing import Any, Self

Responder = Callable[[str, dict[str, Any]], list[dict[str, Any]]]


def _no_rows(query: str, params: dict[str, Any]) -> list[dict[str, Any]]:
    return []


class FakeSession:
    def __init__(self, driver: FakeDriver):
        self._driver = driver

    def __enter__(self) -> Self:
        return self

    def __exit__(self, *exc_info: object) -> bool:
        return False

    def run(self, query: str, **params: Any) -> list[dict[str, Any]]:
        self._driver.calls.append((query, params))
        return self._driver.responder(query, params)


class FakeDriver:
    """Records every `session.run(query, **params)` and answers via `responder(query, params)`."""

    def __init__(self, responder: Responder = _no_rows):
        self.responder = responder
        self.calls: list[tuple[str, dict[str, Any]]] = []
        self.closed = False

    def session(self) -> FakeSession:
        return FakeSession(self)

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
