# CPID-15 — Add logging to the core modules

Status: spec-approved · Risk: low · Jira: CPID-15

## Problem

Verified on main before this change: 0 of 14 modules in `chatpid/` imported `logging`. Failures only
surfaced as strings inside LLM tool output (`agent.py::_safe_tool`) or were swallowed silently
(`cypher_rag.py`'s retry/fallback paths). There was no way to see, from logs, that a tool failed, that
CypherRAG fell back to ContextRAG, or that an upload failed to parse — only what the client was told,
which is deliberately generic (CPID-13/CPID-20 scrub filesystem paths from client-facing errors).

## Users and context

Anyone running the API or scripts locally or in a container, needing to diagnose a failure after the
fact. Code: `chatpid/agent.py` (`_safe_tool`), `chatpid/api.py` (`/ask`, `/ingest`), `chatpid/cypher_rag.py`
(the two swallowed-exception branches in `cypher_rag()`), plus a module logger in every other core module
so later work has somewhere to log from.

## Goals and non-goals

**Goals**
- A module logger (`logging.getLogger(__name__)`) in every core module.
- `_safe_tool` logs the exception with a stack trace before returning its error string to the LLM.
- Both swallowed `except Exception` branches inside `cypher_rag()` log at WARNING or above.
- `/ask` logs which tools were used and how long the call took, without the question or the answer text.
- The upload-parse failure in `/ingest` is logged with its traceback (filesystem path included) even
  though the client only gets a generic message.
- Level configurable via an environment variable, default INFO; no secrets or full prompts at INFO.

**Non-goals**
- Structured/JSON logging, log shipping, or a logging framework beyond the standard library.
- Changing what any endpoint returns to the client (CPID-13/CPID-20's generic error messages are kept).
- Logging in `benchmark.py`, `eval.py`, `scoring.py` (already use `print`, not in scope here).

## Requirements

- R1. `chatpid/logging_config.py`: `configure_logging()` reads `CHATPID_LOG_LEVEL` (default INFO, unknown
  values fall back to INFO with a warning), sets the `chatpid` logger's level, and attaches one stderr
  handler if the root logger has none (idempotent — no duplicate handlers on repeat calls).
- R2. Every module in `CORE_MODULES` (`agent`, `api`, `context_rag`, `cypher_rag`, `ingest`, `llm`,
  `path_rag`, `semantic_enrichment`, `vector_rag`) defines `logger = logging.getLogger(__name__)`.
- R3. `agent.py::_safe_tool`'s wrapper logs the failing tool's name and exception type at ERROR (with
  `exc_info`) before returning the truncated error string; a successful call logs nothing at WARNING+.
- R4. `cypher_rag()`'s two swallowed `except Exception` blocks (after the first execute failure, and after
  the retry-on-empty-result) each log at WARNING+; the first carries the original exception in the message,
  the second attaches `exc_info`.
- R5. `api.py` calls `configure_logging()` at import time; `/ask` logs the tool names and elapsed time at
  INFO after the agent call, never the question or the answer; `/ingest`'s parse-failure branch logs the
  exception with `exc_info` at WARNING, while the HTTP response stays the existing generic message.

## Acceptance criteria

- AC1. Every module in `CORE_MODULES` has `module.logger` as a `logging.Logger` named `chatpid.<module>`;
  `resolve_level` maps known level names case-insensitively and defaults to INFO for anything else;
  `configure_logging()` is idempotent (second call adds no second handler) and uses the env var.
- AC2. `agent._safe_tool("X", boom)()` where `boom` raises leaves exactly one ERROR+ record named
  `chatpid.agent`, naming the tool, with `exc_info` set to the real exception type; a successful call
  leaves no WARNING+ record.
- AC3. With `execute_cypher` always raising, `cypher_rag()` falls back and leaves exactly two WARNING+
  records (both named `chatpid.cypher_rag`, the second with `exc_info`); with it returning `[]` then
  raising on retry, at least one WARNING+ record is left; the happy path leaves none.
- AC4. `POST /ask` leaves an INFO+ record containing the tool name used, but never the posted question
  text or the agent's answer text (including text echoed inside a tool result). `POST /ingest` with a
  parser that raises leaves exactly one WARNING+ record named `chatpid.api` with `exc_info` set, while the
  HTTP response body never contains the path the exception mentioned.
- AC5. The full suite passes; `ruff check .` and `ruff format --check .` are clean.
