# CPID-16 — Add tests for the untested modules: api, ingest, agent, vector_rag, semantic_enrichment

Status: spec-approved · Risk: low · Jira: CPID-16
Created: 2026-10-05 · Slug: tests-untested-modules

## Problem

`tests/` covers only context_rag, cypher_rag and path_rag. The HTTP API, ingestion, the agent wiring, VectorRAG
and semantic enrichment have no tests, so the open API bugs (CPID-12, CPID-14) and any refactor of these
modules cannot be made safely: nothing says what "unchanged" means.

## Users and context

Engineers and agents changing `chatpid/api.py`, `ingest.py`, `agent.py`, `vector_rag.py`,
`semantic_enrichment.py`. Existing style: pytest, `MagicMock` driver (see `tests/test_path_rag.py`), CI runs
`uv run pytest -q` with no secrets, Neo4j or network (`.github/workflows/ci.yml`).

## Goals and non-goals

**Goals**
- Characterise current behaviour of the five modules with fast, deterministic tests.
- A shared recording fake driver/LLM so later bug fixes can be test-first.

**Non-goals**
- No source changes and no bug fixes (known-buggy behaviour is not pinned as correct, see Assumptions).
- No tests that need Neo4j, an LLM key or network; no coverage target.
- `/pid/svg` already has tests (CPID-13).

## Requirements

- R1. `/ask`, `/graph`, `/ingest`, `/health`, `/pid/files` must be covered through FastAPI `TestClient` with the agent, Neo4j driver, LLM and DEXPI loader faked.
- R2. `ingest.py` must be covered: label/relationship sanitising, per-document clearing, `document_id`/`level` tagging, tag computation, DEXPI wrappers, plus one run on the small tracked DEXPI sample.
- R3. `agent.py` must be covered: `_safe_tool`, the four tools' delegation and error handling, and agent wiring.
- R4. `vector_rag.py` and `semantic_enrichment.py` must be covered with a fake embedding function and fake LLM.
- R5. All new tests must run in CI without secrets, Neo4j or network, and must not sleep.

## Acceptance criteria

- AC1. (R1) `tests/test_api.py` asserts: `/ask` answer, tools and touched nodes, prompt prefixes and recursion limit 25, missing question 422, agent failure 500 without echoing the exception; `/graph` node/edge shape, hidden `embedding`/`level` props, `document_id` scoping, empty graph, bad `limit` 422; `/ingest` three levels under one new 8-char document id, non-xml 400, parse failure 400, missing file 422; `/health`; `/pid/files`.
- AC2. (R2) `tests/test_ingest.py` asserts the statements sent to a recording driver: DETACH DELETE scoped by level and document first, MERGE with `Node`-first labels, `level`/`document_id`/`element_id`/`tag` props, hostile label/rel-type text sanitised, non-primitive values JSON-encoded, empty graph only clears; `get_driver` settings; the real sample file yields 3 non-empty levels.
- AC3. (R4) `tests/test_vector_rag.py` and `tests/test_semantic_enrichment.py` assert embedding calls, stored vectors, index DDL, result mapping and text formatting, enrichment prompts, write-back, LLM failure recorded and loop continues, delay via patched sleep.
- AC4. (R3) `tests/test_agent.py` asserts `_safe_tool` result/error/truncation/KeyboardInterrupt behaviour and that each tool delegates with the driver and arguments and returns an error string when the underlying call raises.
- AC5. (R5) `uv run pytest -q` passes in CI (Linux, no secrets, no Neo4j); nothing in the new tests opens a socket or needs `.env`. No test requires Neo4j, so no Neo4j marker is added.
- AC6. (failure paths, R1-R4) Each module's tests include at least one negative case (listed in test-plan.md) and a mutation audit shows the suite fails when the behaviour is broken.

## Edge cases and failure modes

- Module-level state in `api.py` (`_driver`, `_agent`, `_last_*`) must be restored after each test (monkeypatch).
- `get_settings` is `lru_cache`d: tests that change env vars clear the cache before and after.

## Non-functional requirements

- Each file runs in well under 30 s locally; no real sleeps; no secrets in fixtures.

## Assumptions

- The module-global request state in `/ask` (CPID-14) is not asserted, so the later fix can change it without breaking these tests; tests go through HTTP.
- Neo4j-dependent tests are out of scope, so the "marked and skipped by default" clause is satisfied vacuously (none exist).
- `vector_rag` returning an empty label for a node with only the `Node` label is the behaviour after CPID-1 and is pinned.

## Risks and dependencies

Low: test-only. Tests characterise today's behaviour, including things CPID-12/14 will change; those assertions are kept off the buggy parts.
