# CPID-12 — Test plan: CypherRAG read-only

Status: implementing · Risk: high · Jira: CPID-12

Test framework and conventions found: pytest in `tests/`, recording `tests/fakes.py::FakeDriver` (now able to model a read-only server), `monkeypatch` for the LLM-facing functions; command `.venv/Scripts/python.exe -m pytest -q`.

| AC | Level | Test (name/path) | Happy | Boundary | Negative | Status |
|----|-------|------------------|-------|----------|----------|--------|
| AC1 | unit | tests/test_cypher_rag_readonly.py::test_execute_cypher_opens_a_read_access_session_and_a_read_transaction | read query returns rows; one session with `default_access_mode=READ`; 1 read, 0 write transactions | n/a: single query | n/a: see AC2 | verified |
| AC1 | unit | tests/test_cypher_rag_readonly.py::test_every_session_the_module_opens_is_read_only | schema introspection, label list and execute all open `READ` sessions | empty graph (no rows) | n/a: no negative input | verified |
| AC1 | integration | tests/test_cypher_rag_readonly.py::test_cypher_rag_pipeline_runs_the_generated_query_in_a_read_transaction | full pipeline with stubbed LLM runs the generated query as a read transaction | n/a: single run | n/a: no negative input | verified |
| AC2 | unit | tests/test_cypher_rag_readonly.py::test_write_that_evades_the_regex_is_rejected_by_the_read_only_database_layer, ::test_regex_gaps_are_real_so_the_database_layer_is_needed | n/a: negative-only | mixed case and spacing (`call   GDS.pageRank.WRITE ( 'g' )`) | 6 regex-evading statements -> `ClientError`, 0 write transactions; regex alone does not raise | verified |
| AC2 | unit | tests/test_cypher_rag_readonly.py::test_database_layer_rejects_even_when_the_regex_layer_is_bypassed, ::test_the_fake_would_have_let_the_write_through_in_a_default_write_session | control: default session accepts the statement | n/a: single case | `CREATE` with regex patched out -> `ClientError` | verified |
| AC2 | unit | tests/test_cypher_rag_readonly.py::test_regex_still_rejects_obvious_writes_before_touching_the_database, ::test_a_database_rejection_makes_cypher_rag_fall_back_instead_of_writing | n/a: negative-only | n/a: single cases | `CREATE`/`SET`/`DETACH DELETE` -> `ValueError`, no session; DB refusal -> fallback, nothing written | verified |
| AC2 | integration (live) | tests/test_cypher_rag_live.py::test_neo4j_itself_refuses_a_write_even_with_the_regex_layer_bypassed, ::test_a_read_query_works_through_the_read_transaction | `RETURN 1` works | n/a: single case | `CREATE (n:CPID12Probe)` with the regex bypassed -> `ClientError`, 0 probe nodes | written, NOT run (no Neo4j here) |
| AC3 | unit | tests/test_cypher_rag.py (all) | existing CypherRAG tests pass | n/a: unchanged | n/a: unchanged | verified |

## Regression risk

`tests/test_cypher_rag.py::TestCypherInjectionLegitimateQueries::test_legitimate_match_return_passes` used a MagicMock session whose `run` returned rows; `execute_read` needs a callback, so it now uses `FakeDriver` (same input, same asserted output). Other tests using `FakeDriver` (context_rag, path_rag, vector_rag, semantic_enrichment, api) are unaffected: the fake's defaults are unchanged.

## Untestable AC

AC2 against a real database cannot run in this environment (Docker daemon down, Neo4j not running). How to run: `docker compose up -d neo4j`, then `CHATPID_LIVE_NEO4J=1 uv run python -m pytest tests/test_cypher_rag_live.py -q`. Until someone has run it, "Neo4j itself refuses" is an assumption based on the driver's documented read-access behaviour.

## Manual checks

None beyond the live test above.

## Audit (after implementation)

Red first: 11 of the 21 new tests failed on the old code. Mutations on the fixed code, each caught: (M1) `_read_session` returns `driver.session()` -> 2 failed (session-mode tests); (M2) `execute_read` replaced by `execute_write` -> 10 failed; (M3) `_get_label_list` opens a default session -> 1 failed (`test_every_session_the_module_opens_is_read_only`); (M4) regex call removed from `execute_cypher` -> 6 failed (obvious-write and injection tests). Full suite after the fix: 212 passed, 3 skipped (symlink on Windows, 2 live-Neo4j tests).
