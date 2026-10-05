# CPID-13 — Test plan: path traversal in /pid/svg

Status: plan-approved · Risk: high · Jira: CPID-13

Test framework and conventions found: pytest in `tests/`, `fastapi.testclient.TestClient`, loader and renderer replaced by fakes through `monkeypatch`; command `.venv/Scripts/python.exe -m pytest -q`.

| AC | Level | Test (name/path) | Happy | Boundary | Negative | Status |
|----|-------|------------------|-------|----------|----------|--------|
| AC1 | integration | tests/test_api_pid_svg.py::test_valid_file_name_is_served, ::test_real_reference_pid_renders | `good.xml` -> 200 image/svg+xml, loader gets the allowed dir; real `C03V04-VER.EX02.xml` renders | n/a: single valid names | n/a: see negatives below | verified |
| AC1 | integration | tests/test_api_pid_svg.py::test_traversal_and_bad_names_are_rejected | n/a: negative-only | `..`, empty, `secret.txt`, `good.XML.txt` -> 4xx | `../../outside/secret.xml`, `..\..\`, `../raw/../../outside/...` -> 4xx, loader never called | verified |
| AC1 | integration | tests/test_api_pid_svg.py::test_absolute_path_is_rejected | n/a: negative-only | n/a: single value | absolute path to an existing outside .xml -> 4xx | verified |
| AC1 | integration | tests/test_api_pid_svg.py::test_url_encoded_traversal_is_rejected | n/a: negative-only | NUL byte, double-encoded `%252f` -> 4xx | `..%2f`, `%2e%2e%2f`, `..%5c` -> 4xx | verified |
| AC1 | integration | tests/test_api_pid_svg.py::test_symlink_pointing_outside_is_rejected | n/a: negative-only | n/a: single case | symlink inside allowed dir to outside file -> 4xx (skips only where symlinks cannot be created) | verified |
| AC2 | integration | tests/test_api_pid_svg.py::test_missing_file_is_404_without_paths, ::test_render_failure_does_not_leak_exception_text, plus the leak asserts inside every rejection test | 404 body has no path | n/a: bodies | forced loader exception text (`/secret/place`) absent from the 500 body | verified |

## Regression risk

`/pid/files` and the frontend URL builder are unchanged. The 38 existing tests must stay green (they are: 56 passed, 1 skipped overall). Behaviour change: invalid names now 400 instead of 404.

## Untestable AC

None.

## Manual checks

None.

## Audit (after implementation)

Red first: on main (before the fix) 16 of the new tests failed, the traversal ones with `assert 400 <= 200` (the old code served the outside file); the other failures were the path leak in the 404/500 body. Green after the fix: 18 passed, 1 skipped locally (symlink, Windows without privilege); the CI log is checked to confirm the symlink test ran on Linux.
