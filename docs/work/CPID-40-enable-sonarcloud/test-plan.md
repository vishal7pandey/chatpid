# CPID-40 — Test plan: Enable SonarCloud

Status: draft · Risk: low · Jira: CPID-40

This is a CI configuration change: no new application code, so no new unit tests. The checks below are
run for real and recorded in the Audit section.

Test framework and conventions found: pytest via `uv run python -m pytest -q` (backend, `tests/`); ruff via
`uv run ruff check .`; factory gate `python .factory/verify.py`; CI workflows `ci`, `factory-verify`, `sonar`.

| AC | Level | Test (name/path) | Happy | Boundary | Negative | Status |
|----|-------|------------------|-------|----------|----------|--------|
| AC1 | integration | `sonar-project.properties` read and `sonar` job guard | no `REPLACE_ME`, key `vishal7pandey_chatpid`, python 3.12 | guard's `REPLACE_ME` grep ignores comment lines | n/a: covered by AC3 simulation | planned |
| AC2 | integration | local run of the new test command; CI job `sonar` test step | 241 passed, 3 skipped, `coverage.xml` written | `--frozen` so the lock is not modified | covered by AC3 deliberate break | planned |
| AC3 | integration | guard script with `SONAR_TOKEN` empty; CI job `sonar` on the PR | token set: guard enables, scan runs | token empty: notice printed, exit 0, `enabled=false` | break the test step (`pytest --no-such-flag`): job red; restore: green | planned |
| AC4 | manual | public SonarCloud API after the merge | `search_projects` shows `vishal7pandey_chatpid`, gate status and issue count read | n/a: read-only | n/a: read-only | planned |
| AC5 | manual | scan log on the PR | scan is not refused with an Automatic Analysis error | n/a: single setting | if refused for that reason, the ticket records it and stays In Progress | planned |

## Regression risk

`ci.yml` is untouched. The backend tests must stay at 241 passed, 3 skipped. `uv.lock` and `pyproject.toml`
must stay unchanged.

## Untestable AC

None.

## Manual checks

AC4: after merge run three unauthenticated GETs against `sonarcloud.io/api` (`components/search_projects`,
`qualitygates/project_status`, `issues/search`) with python urllib; expect the project listed, a gate
status and an issue total. AC5: read the PR's `sonar` job log; expect an analysis upload without an
"Automatic Analysis" refusal.

## Audit (after implementation)

Filled in after the checks run.
