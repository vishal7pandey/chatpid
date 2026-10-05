# CPID-14 — Request state leaks between users

Status: spec-approved · Risk: medium · Jira: CPID-14

## Repro

Environment: main @ b44257c (before the fix), Windows, Python 3.14, FastAPI TestClient with a fake agent and fake Neo4j driver.

1. Call `POST /ask` once with any question.
2. Inspect `chatpid.api`: `_last_question`, `_last_answer`, `_last_tools`, `_last_graph_nodes` now hold that caller's data, visible to every other request in the process.

Automated repro (fails on the old code, passes after the fix):

- `.venv/Scripts/python.exe -m pytest tests/test_api_stateless.py -q`; before the fix `test_ask_leaves_no_per_request_state_in_the_api_module` and `test_api_module_has_no_last_request_globals_or_lock` fail (module state changes after `/ask`; `['_state_lock', '_last_...']` still present).

Reproducibility: always.

## Expected

The API is stateless per request: everything a client needs comes back in the `/ask` response (`graph_node_ids`), and `/graph` depends only on its own query parameters (ticket AC1, AC2, AC3).

## Actual

`chatpid/api.py` kept four module-level globals behind a lock and `/ask` overwrote them on every call. Correction to the ticket text, found while diagnosing: on this commit nothing in the API reads them back. `/graph` never used them (its docstring claimed it did), and the frontend already takes the touched tags from the `/ask` response (`ChatPanel` `onTouchedNodes` -> page state -> `GraphPanel highlightedNodes`). So there was no observable cross-user leak today; the state was dead, but it was a trap: the first change to make `/graph` "highlight the last answer" (as its docstring said) would have leaked one user's nodes to everyone.

## Root cause (with evidence)

- Where: `chatpid/api.py` module globals (old lines 47-55) and the write block at the end of `ask()`.
- Why it fails: design for a "last answer" cache that is global to the process instead of per request.
- Introduced by: the initial `/ask` + `/graph` design; always present.
- Evidence: `grep -n "_last_" chatpid tests` showed writes in `ask()` only; no reads outside the test fixture that resets them.

## Blast radius

- Nothing else in `chatpid/` keeps request state: module-level mutable objects are the lazily built singletons `_driver` / `_agent` (shared by design) and caches `_embedder` (vector_rag) and `_semantic_model` (scoring), which hold models, not user data.
- Frontend: already stateless in the way the ticket prefers (the client holds the touched tags in React state per tab), so it needs no code change; nothing in `frontend/lib/api.ts` or the components referenced the removed state.

## Regression criterion (AC1)

AC1: no module-level mutable per-request state remains in `api.py`: `tests/test_api_stateless.py::test_api_module_has_no_last_request_globals_or_lock` and `::test_ask_leaves_no_per_request_state_in_the_api_module` (deep-copies every module-level str/list/dict/set before and after `/ask`) pass after the fix and fail on the old code.

AC2: `::test_two_overlapping_asks_each_get_only_their_own_nodes` (two threads held inside the agent at the same time by a barrier; each response carries only its own answer, tool calls and node tags) and `::test_interleaved_ask_graph_sequences_do_not_see_each_others_nodes` (`/graph` output is identical before and after two different asks and contains none of their tags).

AC3: the frontend still highlights from the `/ask` response; verified by reading the data flow (`ChatPanel` -> `page.tsx` -> `GraphPanel`) and unchanged `lib/api.ts` contract (`graph_node_ids`). The frontend build could not be run here: `frontend/node_modules` is broken since the folder move and `pnpm` wants to purge and reinstall it; no frontend file changed in this PR.

## Fix constraints

Delete the four globals, the lock, the write block and the stale docstring claim; keep `AskResponse`, URLs and the lazily built `_driver` / `_agent`. No new dependency.

## Risks

Medium (API module change on the main endpoint), small diff. Rollback: revert the commit.
