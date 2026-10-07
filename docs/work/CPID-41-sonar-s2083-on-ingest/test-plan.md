# CPID-41 — Test plan: Sonar S2083 on ingest

Status: draft · Risk: high · Jira: CPID-41

Test framework and conventions found: pytest in `tests/`, `fastapi.testclient.TestClient`, loader/graph/Neo4j replaced by fakes via `monkeypatch`, temp dir moved under `tmp_path` by the `sandbox` fixture; command `uv run python -m pytest -q`.

| AC | Level | Test (name/path) | Happy | Boundary | Negative | Status |
|----|-------|------------------|-------|----------|----------|--------|
| AC1 | integration | tests/test_api_ingest_filename.py::test_write_is_contained_in_the_temp_dir_at_the_point_of_use | n/a: negative-only (the guard must stay silent for the constant name, covered by AC2 tests) | `../escape.xml` (one level up) | `../../escape.xml`, `sub/../../escape.xml`: 500, no `write_bytes`, nothing left on disk, no path in the body | verified |
| AC2 | integration | tests/test_api_ingest_filename.py::test_upload_bytes_only_ever_land_in_the_fixed_file_of_the_endpoint_temp_dir | `plant.xml` writes `<temp dir>/upload.xml` | `%2e%2e%2fx.xml` (encoded, literal name) | `../x.xml`, `..\..\x.xml`, `/etc/x.xml`, `C:/Windows/x.xml`, UNC, `..%5cx.xml`, double-encoded, NUL: every write target is `upload.xml` in the endpoint temp dir, nothing outside | verified |
| AC2 | integration | tests/test_api_ingest_filename.py::test_hostile_upload_content_is_data_never_a_path | content `../../x.xml` stored byte for byte in `upload.xml` | NUL bytes | `/etc/passwd`, `C:\Windows\win.ini`, XXE doctype text: one write, to `upload.xml` | verified |
| AC2 | integration | tests/test_api_ingest_filename.py (existing CPID-20 tests) and tests/test_api.py /ingest tests | valid upload ingests | n/a: covered by the CPID-20 file | traversal names rejected 4xx | verified |
| AC3 | manual | SonarCloud issue AaESHd3k4FTZ_gsvTVdz re-queried after the push scan on main | n/a: closure check | n/a | status must read CLOSED, otherwise dismissal proposal and ticket stays open | planned (after merge) |

## Regression risk

`/ingest` behaviour for valid uploads is unchanged; the CPID-20 tests and `tests/test_api.py` ingest tests must stay green.

## Untestable AC

AC3 is a scanner state, not testable in the suite; it is checked by re-querying the issue.

## Manual checks

After merge and the SonarCloud scan on main: `GET https://sonarcloud.io/api/issues/search?issues=AaESHd3k4FTZ_gsvTVdz`, expect `status` CLOSED.

## Audit (after implementation)

Mutation audit (2026-10-06): (1) old code (no guard at the sink): the 3 `test_write_is_contained_in_the_temp_dir_at_the_point_of_use` cases fail (`assert 200 == 500`); the 13 hostile-name and 5 hostile-content cases pass on old and new code, which shows the endpoint was already safe for client input. (2) Fix kept but the `startswith` check replaced by `if False:`: the same 3 cases fail, so the check itself is pinned. (3) Fix restored: tests/test_api_ingest_filename.py 51 passed; full suite 262 passed, 3 skipped; ruff check and format clean. AC3 is checked after merge.

## Follow-up (PR 26)

PR 25 closed Sonar issue `AaESHd3k4FTZ_gsvTVdz` but the push scan reported the same rule as a new issue `AaESVCox-B_YsUej5pDi` at the moved line (api.py:364), same flow. PR 26 puts `write_bytes` inside the true branch of the single inline `os.path.realpath` + `startswith(base + os.sep)` check; the PR scan then showed 0 issues. Tests unchanged (262 passed, 3 skipped); the 3 contained-write cases still fail when the check is neutralised (audit unchanged).
