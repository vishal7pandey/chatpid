# CPID-14 — Test plan: stateless API

Status: implementing · Risk: medium · Jira: CPID-14

Test framework and conventions found: pytest in `tests/`, `fastapi.testclient.TestClient`, `tests/fakes.py::FakeDriver`, hand-written fake agents; command `.venv/Scripts/python.exe -m pytest -q`.

| AC | Level | Test (name/path) | Happy | Boundary | Negative | Status |
|----|-------|------------------|-------|----------|----------|--------|
| AC1 | unit | tests/test_api_stateless.py::test_api_module_has_no_last_request_globals_or_lock | no `_last_*` / `_state_lock` attribute in `chatpid.api` | n/a: single check | old code has all five attributes -> fails | verified |
| AC1 | integration | tests/test_api_stateless.py::test_ask_leaves_no_per_request_state_in_the_api_module | module-level str/list/dict/set equal before and after `/ask` | n/a: single call | any new global written by `/ask` -> fails | verified |
| AC2 | integration | tests/test_api_stateless.py::test_two_overlapping_asks_each_get_only_their_own_nodes | alice gets `T4750`, bob gets `P4711`, own answers and tool args | n/a: two callers | shared-state mutation returns bob alice's node -> fails | verified |
| AC2 | integration | tests/test_api_stateless.py::test_interleaved_ask_graph_sequences_do_not_see_each_others_nodes | `/graph` identical before/after two asks; asks return their own tags | n/a: single sequence | `/graph` fed from ask state -> fails | verified |
| AC3 | manual | read `ChatPanel.tsx` -> `app/page.tsx` -> `GraphPanel.tsx`; `lib/api.ts` unchanged | highlight tags come from `AskResponse.graph_node_ids` | n/a: single flow | n/a: no frontend change | verified (build not run, see below) |

## Regression risk

All `/ask` and `/graph` tests in tests/test_api.py stay green (they only lost the four `_last_*` monkeypatch lines, which no longer have a target). No behaviour change.

## Untestable AC

AC3 build step: `frontend/node_modules` is broken since the folder move (`next` missing) and `pnpm build` tries to purge and reinstall it without a TTY, so `pnpm build` was not run. No frontend file is part of this change.

## Manual checks

AC3: open `frontend/components/ChatPanel.tsx` (`onTouchedNodes?.(res.graph_node_ids)`), `frontend/app/page.tsx` (`highlightedNodes` state), `frontend/components/GraphPanel.tsx` (`highlightSet` from the prop): the tags come from the response, not from server state.

## Audit (after implementation)

Red first: on the old code `test_ask_leaves_no_per_request_state_in_the_api_module` and `test_api_module_has_no_last_request_globals_or_lock` failed; the two behavioural tests passed (the leak was latent, nothing read the globals). Mutations on the fixed code, each caught: (M1) a module global `_m` written by `/ask` -> module-state test fails; (M2) `/ask` returns the node list from that global after a 0.3 s pause -> overlapping-asks test fails (`['T4750'] == ['P4711']`); (M3) `/graph` appends a node tagged from that global -> interleaved ask/graph test fails. Full suite after the fix: 191 passed, 1 skipped.
