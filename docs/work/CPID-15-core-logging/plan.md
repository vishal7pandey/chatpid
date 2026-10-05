# CPID-15 — Plan: logging in the core modules

Status: plan-approved · Risk: low · Jira: CPID-15
Created: 2026-10-05 · Slug: core-logging · Spec: spec.md

## Summary

A small `logging_config.py` entry point, a `logger = logging.getLogger(__name__)` in every core module,
and three call sites that turn an already-caught exception into a log record instead of silence.
**Size:** S

## Current state

- No module in `chatpid/` imports `logging`. `agent.py::_safe_tool` turns every tool exception into a
  string the LLM sees; nothing else records it. `cypher_rag()` has two `except Exception:` blocks that
  discard the exception entirely. `api.py` has no logging setup; its `/ingest` parse-failure branch
  raises a generic `HTTPException` with `from None`, dropping the original traceback.
- Tests live in `tests/`, use `pytest`'s `caplog` fixture, `fastapi.testclient.TestClient`, and
  `tests/fakes.py::FakeDriver`. Command: `uv run python -m pytest -q`.

## Approach

1. `chatpid/logging_config.py`: `resolve_level(value)` (name → level, default INFO) and
   `configure_logging()` (sets the `chatpid` logger's level, adds one named stderr handler if the root
   logger has none, idempotent via a handler-name check).
2. Add `logger = logging.getLogger(__name__)` to the 9 core modules, grouped with their existing imports.
3. `agent.py::_safe_tool`: `logger.exception(...)` inside the `except` block, before building the error
   string. `logger.exception` is only valid inside an `except` block, which it is.
4. `cypher_rag.py::cypher_rag()`: a `logger.warning` call in the outer `except Exception as exc:` (names
   the original exception, triggers the retry) and another in the inner `except Exception:` that follows
   the failed retry-after-empty-result (both inner blocks that fall back after a second failure), the
   second with `exc_info=True`.
5. `api.py`: call `configure_logging()` once at import time; `/ask` logs tool names (not args) and
   elapsed time at INFO after extracting them; `/ingest`'s parse-failure branch logs the exception with
   `exc_info=True` at WARNING before raising the (unchanged) generic `HTTPException`.

**Alternatives rejected**
- A logging framework (structlog, loguru): stdlib `logging` is enough for the stated goals and needs no
  new dependency (autonomy policy: ask first before adding one).
- Logging full tool arguments/results at INFO: the ticket explicitly excludes secrets/full prompts from
  INFO; tool names and counts are enough to diagnose from logs alone.

## Tasks

| # | Task | Files | Serves | Verify by |
|---|------|-------|--------|-----------|
| T1 | `logging_config.py` + its tests | `chatpid/logging_config.py`, `tests/test_logging.py` | AC1 | red then green |
| T2 | Module loggers in the 8 remaining core modules | `chatpid/{context_rag,ingest,llm,path_rag,semantic_enrichment,vector_rag}.py` | AC1 | test_core_module_has_a_module_logger |
| T3 | `_safe_tool` logging | `chatpid/agent.py` | AC2 | test_safe_tool_logs_* |
| T4 | `cypher_rag()` swallowed-exception logging | `chatpid/cypher_rag.py` | AC3 | test_cypher_rag_logs_* |
| T5 | `api.py` setup + `/ask` + `/ingest` logging | `chatpid/api.py` | AC4 | test_ask_logs_*, test_parse_failure_* |

## Data, API and migration impact

None. No response shape changes; `/ingest` and `/pid/svg` keep their existing generic error bodies.

## Security and failure modes

This closes a visibility gap, not a new risk: the filesystem path now logged on an ingest parse failure
was already being computed (just discarded) and never reaches the HTTP response, matching CPID-13/CPID-20.
`CHATPID_LOG_LEVEL` read once; an unrecognised value falls back to INFO with a warning rather than crashing.

## Rollout and rollback

Merge; revert to undo. No migration, no config required (default level is INFO without `.env` changes).

## Risks and open points

- `logger.exception` only attaches `exc_info` when called inside the `except` block that caught it; this
  holds everywhere it's used here (verified by reading each call site).
- Scope: the ticket's AC2/AC3 name `_safe_tool` and `cypher_rag.py` specifically; `/ask`/`/ingest` logging
  in `api.py` is also added since AC1 already requires a logger there and it is the cheapest way to prove
  AC1 is useful, not just present. `/pid/svg`'s analogous swallowed exception is left alone — out of the
  ticket's stated scope.
