# CPID-16 — Test plan: tests for the untested modules

Status: plan-approved · Risk: low · Jira: CPID-16

Test framework and conventions found: pytest, `tests/` package, files `test_<module>.py`, plain functions and `monkeypatch`; run all with `.venv/Scripts/python.exe -m pytest -q`. Fakes live in `tests/fakes.py`.

| AC | Level | Test (name/path) | Happy | Boundary | Negative | Status |
|----|-------|------------------|-------|----------|----------|--------|
| AC1 | integration | tests/test_api.py::test_ask_returns_answer_tools_and_touched_nodes, ::test_ask_prefixes_the_prompt_with_document_and_level_and_bounds_the_loop | answer, tools, nodes, prompt prefix, recursion_limit 25 | default level only; empty level sends bare question | missing question 422; agent failure 500 without exception text; final answer missing gives a clear message | verified |
| AC1 | integration | tests/test_api.py::test_graph_* | nodes/edges shape, internal props hidden, document scoping | empty graph; limit passed | `limit=lots` 422, no query run | verified |
| AC1 | integration | tests/test_api.py::test_ingest_*, ::test_health, ::test_pid_files_* | three levels under one 8-char id; `/pid/files` dedup across dirs | no data dirs gives empty list | non-xml 400; parse failure 400 with nothing loaded; no file 422 | verified |
| AC2 | unit | tests/test_ingest.py (helpers, clear_level, load_graph, wrappers) | statements carry level/document_id/element_id/tag; Node-first labels | empty graph only clears; default document id | hostile label and relationship text sanitised | verified |
| AC2 | integration | tests/test_ingest.py::test_real_sample_loads_builds_three_levels_and_writes_scoped_statements | real pyDEXPI on the C03V04 sample | n/a: single file | n/a: no input | verified |
| AC3 | unit | tests/test_vector_rag.py | embedder built once from settings; vectors stored; index DDL; results and text | no enriched nodes writes nothing; labels `[]`/None/Node-only give empty label; 200-char cap | no hits returns "No relevant nodes found." | verified |
| AC3 | unit | tests/test_semantic_enrichment.py | stripped semantics written back; prompts carry node context | 3000-char context cap; no nodes; delay via patched sleep | LLM failure recorded as ERROR, loop continues, nothing written for it | verified |
| AC4 | unit | tests/test_agent.py | tools delegate with driver and args; wiring of four tools and prompt | defaults (conceptual/graph, depth, breadth) | every tool turns an exception into `[Tool error] ...`; long message cut at 300; KeyboardInterrupt not swallowed | verified |
| AC5 | integration | CI job `test` | green on Linux with no secrets | n/a: single job | n/a: no secrets present proves it | verified |
| AC6 | manual | mutation audit (scratch script, not committed) | n/a: audit | n/a: audit | 22 deliberate source mutations, each made at least one test fail | verified |

## Regression risk

No source files change, so existing behaviour cannot regress. Existing 57 tests must stay green (they do).
CPID-12 (CypherRAG) and CPID-14 (api globals) will touch code near these tests; the tests avoid asserting the buggy parts.

## Untestable AC

None.

## Manual checks

AC6: the audit script mutated one expression at a time in api.py, ingest.py, agent.py, vector_rag.py and semantic_enrichment.py (for example recursion limit 25 to 10, dropping the `document_id` property, `raise` in `_safe_tool`, `sem[:200]` to `[:300]`, context cap 3000 to 4000) and ran the matching test file; all 22 mutants were killed and the sources were restored afterwards (`git status` clean for chatpid/).

## Audit (after implementation)

See AC6 above: 22 of 22 mutants killed. In the first pass two mutations were reported as not found by my script (line endings and a reformatted line); they were re-run with corrected patterns and both were killed.
