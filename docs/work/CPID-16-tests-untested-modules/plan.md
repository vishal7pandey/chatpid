# CPID-16 — Plan: tests for the untested modules

Status: plan-approved · Risk: low · Jira: CPID-16
Created: 2026-10-05 · Slug: tests-untested-modules · Spec: spec.md

## Summary

Add one test file per module plus a shared `tests/fakes.py` (recording fake Neo4j driver, fake LLM). API first,
then ingest, agent, vector_rag, semantic_enrichment. Source code is not touched.

**Size:** M

## Current state

`tests/` holds test_context_rag.py, test_cypher_rag.py, test_path_rag.py, test_api_pid_svg.py (CPID-13). The five
modules are in `chatpid/`. `api.py` keeps `_driver`, `_agent`, `_last_*` globals; `vector_rag._embedder` is a lazy
global; `get_settings()` is cached. Commands: `.venv/Scripts/python.exe -m pytest -q`, `python -m ruff check .`.

## Approach

Fake at the boundary only: the Neo4j driver (`FakeDriver.session().run()` records `(query, params)` and answers
through a responder), the LLM (`FakeLLM.invoke`), the embedder (`FakeEmbedder`), `ProteusSerializer`/loader and
`create_react_agent`. Everything inside the repo runs for real. Use `monkeypatch` for module globals so state is
restored.

**Alternatives rejected**
- A live Neo4j in CI: needs Docker services, slow, and the ticket says no Neo4j in CI.
- `MagicMock` everywhere: asserts call counts, not the Cypher text and parameters that matter.

## Tasks

| # | Task | Files | Serves | Verify by |
|---|------|-------|--------|-----------|
| T1 | Shared fakes | tests/fakes.py | AC1-AC4 | imported by the tests below |
| T2 | API tests | tests/test_api.py | AC1 | 28 tests pass |
| T3 | Ingest tests | tests/test_ingest.py | AC2 | 28 tests pass |
| T4 | Agent tests | tests/test_agent.py | AC4 | 16 tests pass |
| T5 | VectorRAG and enrichment tests | tests/test_vector_rag.py, tests/test_semantic_enrichment.py | AC3 | 29 tests pass |
| T6 | Mutation audit, ruff, CI | whole repo | AC5, AC6 | 22 mutations all killed, CI green |

## Data, API and migration impact

None (tests only).

## Security and failure modes

No secrets, no network. Tests check that an agent failure does not echo exception text in the HTTP body.

## Rollout and rollback

Merge; revert the commit to undo.

## Risks and open points

- Tests that pin current behaviour may need updating when CPID-12/14/18 land; they were kept off the known-buggy parts.
