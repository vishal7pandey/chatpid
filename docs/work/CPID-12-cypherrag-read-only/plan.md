# CPID-12 — Plan: database-enforced read path for CypherRAG

Status: plan-approved · Risk: high · Jira: CPID-12
Created: 2026-10-05 · Slug: cypherrag-read-only · Spec: spec.md

## Summary

Open every CypherRAG session with `READ_ACCESS`, run generated Cypher through `execute_read`, keep the regex as a second layer. Extend the fake driver so tests can model a read-only server; add an opt-in live test.

**Size:** S

## Current state

`chatpid/cypher_rag.py` has three `driver.session()` calls; `execute_cypher` does regex validation then `session.run`. `tests/fakes.py::FakeDriver.session()` takes no arguments and has no `execute_read`.

## Approach

1. Red: `tests/test_cypher_rag_readonly.py` (11 failures on old code).
2. `_read_session(driver)` helper (`default_access_mode=READ_ACCESS`); use it for the three sessions; `execute_cypher` calls `session.execute_read(fn)` where `fn` consumes the rows inside the transaction.
3. `tests/fakes.py`: `session(**config)` recorded, `execute_read` / `execute_write`, optional `write_detector` that raises `ClientError` for writes in read-only sessions/transactions.
4. Update the one MagicMock-based test that cannot run `execute_read`.
5. Opt-in live test `tests/test_cypher_rag_live.py`.

**Alternatives rejected**
- `session.run` inside a `READ_ACCESS` session: also enforced by the server, but `execute_read` is the explicit managed read transaction the ticket asks for and retries transient errors.
- Dropping the regex: it still gives a clear early error and a second layer.
- A read-only Neo4j user: stronger, but infrastructure/credentials; left to the owner.

## Tasks

| # | Task | Files | Serves | Verify by |
|---|------|-------|--------|-----------|
| T1 | Failing tests (red) | tests/test_cypher_rag_readonly.py, tests/fakes.py | AC1, AC2 | 11 failed |
| T2 | Read-only sessions and read transaction | chatpid/cypher_rag.py | AC1, AC2 | tests green |
| T3 | Keep existing tests green | tests/test_cypher_rag.py | AC3 | 212 passed |
| T4 | Opt-in live test and run instructions | tests/test_cypher_rag_live.py | AC2 | skipped without Neo4j; docstring |

## Data, API and migration impact

None.

## Security and failure modes

This is the fix. A database refusal surfaces as an exception, which `cypher_rag()` already turns into a retry and then a ContextRAG fallback; nothing is written.

## Rollout and rollback

Merge; revert to undo.

## Risks and open points

Server-side refusal is unproven here (no Neo4j): covered by the opt-in live test, to be run by someone with Neo4j up.
