# CPID-14 — Plan: make the API stateless

Status: plan-approved · Risk: medium · Jira: CPID-14
Created: 2026-10-05 · Slug: request-state-leak · Spec: spec.md

## Summary

Remove the process-wide "last request" globals and their lock, correct the `/graph` docstring, prove statelessness with tests. The stateless design the ticket prefers already exists in the response contract (`graph_node_ids`), so no API shape change is needed.

**Size:** S

## Current state

`chatpid/api.py` defines `_last_question`, `_last_answer`, `_last_tools`, `_last_graph_nodes`, `_state_lock`; `ask()` writes them; `tests/test_api.py` fixture `client` resets them via monkeypatch. Frontend consumes `graph_node_ids` from `/ask`.

## Approach

1. Red: `tests/test_api_stateless.py` (module-state checks fail on old code).
2. Delete globals, lock, `import threading`, the write block; fix the docstring; drop the four `monkeypatch.setattr(api, "_last_...")` lines from the `client` fixture (they would raise AttributeError).
3. Leave `/graph`, `AskResponse` and the frontend untouched.

**Alternatives rejected**
- Session-id keyed state: adds server state and expiry for no benefit.
- Passing node ids to `/graph` as a parameter: the client already highlights locally; extra API surface for nothing.

## Tasks

| # | Task | Files | Serves | Verify by |
|---|------|-------|--------|-----------|
| T1 | Failing stateless tests | tests/test_api_stateless.py | AC1, AC2 | 2 failed on old code |
| T2 | Remove globals and dead write block | chatpid/api.py, tests/test_api.py | AC1, AC2 | 191 passed |
| T3 | Frontend data-flow check | frontend (read only) | AC3 | spec AC3 note |

## Data, API and migration impact

None: response and request shapes unchanged.

## Security and failure modes

Removes cross-request data sharing (cross-user information exposure class). Concurrency: nothing shared between requests except the driver and agent singletons.

## Rollout and rollback

Merge; revert to undo.

## Risks and open points

Frontend build not runnable locally (broken `node_modules`); frontend untouched, so CI (backend only) is the signal.
