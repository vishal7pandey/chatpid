# CPID-15 — Test plan: logging in the core modules

Status: in-review · Risk: low · Jira: CPID-15

Test framework and conventions found: pytest, `caplog`/`monkeypatch` fixtures, `fastapi.testclient.TestClient`,
`tests/fakes.py::FakeDriver`; command `uv run python -m pytest -q`.

| AC | Level | Test (name/path) | Happy | Boundary | Negative | Status |
|----|-------|------------------|-------|----------|----------|--------|
| AC1 | unit | tests/test_logging.py::test_core_module_has_a_module_logger (parametrized x9) | each of the 9 modules exposes `logger` named `chatpid.<module>` | n/a | n/a | verified |
| AC1 | unit | tests/test_logging.py::test_resolve_level_reads_names_and_defaults_to_info | known names (debug/warning/error), case/whitespace-insensitive | `None`/`""` -> INFO | unknown name -> INFO | verified |
| AC1 | unit | tests/test_logging.py::test_configure_logging_uses_the_env_var_and_is_idempotent | DEBUG from env, level set | second call adds no second handler | n/a | verified |
| AC1 | unit | tests/test_logging.py::test_configure_logging_defaults_to_info_without_the_env_var | no env var -> INFO | n/a | n/a | verified |
| AC1 | unit | tests/test_logging.py::test_configure_logging_warns_and_falls_back_on_an_unknown_level | n/a | n/a | `"loud"` -> INFO + a warning record | verified |
| AC2 | unit | tests/test_logging.py::test_safe_tool_logs_the_exception_with_a_stack_trace_and_still_returns_its_message | n/a: negative-only | n/a | exception -> exactly 1 ERROR+ record, `chatpid.agent`, names the tool, real `exc_info` | verified |
| AC2 | unit | tests/test_logging.py::test_a_successful_tool_call_logs_no_error | success -> no WARNING+ record | n/a | n/a | verified |
| AC3 | unit | tests/test_logging.py::test_cypher_rag_logs_both_swallowed_failures_before_falling_back | n/a: negative-only | n/a | always-raising `execute_cypher` -> exactly 2 WARNING+ records, both `chatpid.cypher_rag`, second has `exc_info` | verified |
| AC3 | unit | tests/test_logging.py::test_cypher_rag_logs_a_failed_retry_after_an_empty_result | n/a | empty result then raise on retry | at least 1 WARNING+ record | verified |
| AC3 | unit | tests/test_logging.py::test_cypher_rag_happy_path_logs_no_warning | results on the first try -> no WARNING+ record | n/a | n/a | verified |
| AC4 | integration | tests/test_logging.py::test_ask_logs_tool_names_and_timing_but_not_the_question_or_the_answer | INFO record contains "CypherRAG" | n/a | the posted question text and the agent's answer/tool-result text are absent from every INFO+ message | verified |
| AC4 | integration | tests/test_logging.py::test_parse_failure_on_ingest_is_logged_with_traceback_but_not_returned | n/a | n/a | parser raises -> exactly 1 WARNING+ record (`chatpid.api`, `exc_info` set); response body never contains the path | verified |
| AC5 | manual | `uv run python -m pytest -q`; `uv run ruff check .`; `uv run ruff format --check .` | all green | n/a | n/a | verified |

## Regression risk

None of the existing tests assert on log output; adding handlers/loggers does not change any return value
or HTTP response. The full suite (238 passed, 2 skipped) is unchanged in count from before this change.

## Untestable AC

None.

## Manual checks

None beyond the AC5 commands above.

## Audit (after implementation)

Each mutation applied to the real file (confirmed changed), the relevant `-k` subset run, then the file
restored from a backup copy (confirmed byte-identical afterwards):

| Mutation | Test(s) run | Result |
|---|---|---|
| M1: delete the `logger.exception(...)` call in `agent.py::_safe_tool` | `-k safe_tool` | `test_safe_tool_logs_the_exception_...` fails (`ValueError: not enough values to unpack`, 0 ERROR+ records) |
| M2: delete the first `logger.warning(...)` in `cypher_rag()`'s outer except | `-k cypher_rag` | `test_cypher_rag_logs_both_swallowed_failures_before_falling_back` fails (only 1 of 2 expected warnings; also surfaces the unhandled `RuntimeError` on the next failure path, confirming the removed log line was masking nothing else) |
| M3: delete the `/ask` `logger.info(...)` call in `api.py` | `-k ask_logs` | `test_ask_logs_tool_names_and_timing_...` fails (`assert 'CypherRAG' in ''`) |
| M4: delete the `/ingest` `logger.warning(...)` call in `api.py` | `-k parse_failure` | `test_parse_failure_on_ingest_...` fails (`ValueError: not enough values to unpack`, 0 WARNING+ records) |

Files restored after each mutation (`diff -q` against the pre-mutation backup showed no difference).
Full suite after restoring: 238 passed, 2 skipped. `ruff check .` and `ruff format --check .`: clean.
