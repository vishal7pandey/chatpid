# CPID-34 — Test plan: path injection alerts in _find_pid_dir

Status: plan-approved · Risk: high · Jira: CPID-34

Test framework and conventions found: pytest in `tests/`, `fastapi.testclient.TestClient`, loader and renderer replaced by fakes via `monkeypatch`; command `uv run python -m pytest -q`.

| AC | Level | Test (name/path) | Happy | Boundary | Negative | Status |
|----|-------|------------------|-------|----------|----------|--------|
| AC1 | unit | tests/test_api_pid_svg.py::test_find_pid_dir_never_touches_files_outside_the_base | n/a: negative-only | `..` (resolves to the parent of the base) | `../../outside/secret.xml`, `../raw/../../outside/secret.xml`: returns None and no `is_file`/`isfile` call on a path outside the allowed dirs | verified |
| AC2 | unit | tests/test_api_pid_svg.py::test_find_pid_dir_still_finds_legitimate_files | `good.xml` -> `data/dexpi_real` | n/a: single valid name | `nope.xml` -> None | verified |
| AC2 | integration | tests/test_api_pid_svg.py (existing CPID-13 tests: test_valid_file_name_is_served, test_real_reference_pid_renders, test_traversal_and_bad_names_are_rejected, test_absolute_path_is_rejected, test_url_encoded_traversal_is_rejected, test_symlink_pointing_outside_is_rejected, test_missing_file_is_404_without_paths) | valid name 200; real reference P&ID renders | `..`, empty | traversal, absolute, encoded, symlink -> 4xx | verified |
| AC3 | manual | alerts 1 and 2 re-queried after the CodeQL run on main | n/a: closure check | n/a | state must read `fixed`, otherwise tickets stay open | planned (after merge) |

## Regression risk

`/pid/svg` and `/pid/files` behaviour is unchanged; the CPID-13 tests above must stay green and the rest of the backend suite
stays at 237 passing.

## Untestable AC

AC3 is a scanner state, not testable in the suite; it is checked by re-querying the alert (manual, below).

## Manual checks

After merge and the CodeQL run on main: `gh api repos/vishal7pandey/chatpid/code-scanning/alerts/1` and `/2`, expect `state: fixed`.

## Audit (after implementation)

Mutation audit (2026-10-05): (1) old code (is_file before the containment check): 3 of the new tests fail (`probed outside the base`). (2) Fix kept but the `startswith` containment check removed: the same 3 tests fail, so the check itself is pinned, not just the order. (3) Fix restored: tests/test_api_pid_svg.py 22 passed, 1 skipped (symlink, Windows); full suite 241 passed, 3 skipped; ruff check and format clean. AC3 is checked after merge by re-querying the alerts.
