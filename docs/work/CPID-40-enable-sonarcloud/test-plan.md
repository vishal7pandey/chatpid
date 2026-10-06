# CPID-40 — Test plan: Enable SonarCloud

Status: draft · Risk: low · Jira: CPID-40

This is a CI configuration change: no new application code, so no new unit tests. The checks below are
run for real and recorded in the Audit section.

Test framework and conventions found: pytest via `uv run python -m pytest -q` (backend, `tests/`); ruff via
`uv run ruff check .`; factory gate `python .factory/verify.py`; CI workflows `ci`, `factory-verify`, `sonar`.

| AC | Level | Test (name/path) | Happy | Boundary | Negative | Status |
|----|-------|------------------|-------|----------|----------|--------|
| AC1 | integration | `sonar-project.properties` read and `sonar` job guard | no `REPLACE_ME`, key `vishal7pandey_chatpid`, python 3.12 | guard's `REPLACE_ME` grep ignores comment lines | n/a: covered by AC3 simulation | verified |
| AC2 | integration | local run of the new test command; CI job `sonar` test step | 241 passed, 3 skipped, `coverage.xml` written | `--frozen` so the lock is not modified | covered by AC3 deliberate break | verified |
| AC3 | integration | guard script with `SONAR_TOKEN` empty; CI job `sonar` on the PR | token set: guard enables, scan runs | token empty: notice printed, exit 0, `enabled=false` | break the test step (`pytest --no-such-flag`): job red; restore: green | verified |
| AC4 | manual | public SonarCloud API after the merge | `search_projects` shows `vishal7pandey_chatpid`, gate status and issue count read | n/a: read-only | n/a: read-only | planned |
| AC5 | manual | scan log on the PR | scan is not refused with an Automatic Analysis error | n/a: single setting | if refused for that reason, the ticket records it and stays In Progress | verified |

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

Run on branch `feature/cpid-40-enable-sonarcloud` (PR 24), 2026-10-06. All rows verified except AC4, which is
recorded on the ticket after the merge.

| AC | Check run | Result |
|----|-----------|--------|
| AC1 | Read `sonar-project.properties` | `sonar.organization=vishal7pandey`, `sonar.projectKey=vishal7pandey_chatpid`, `sonar.python.version=3.12` (CI uses 3.12); no `REPLACE_ME` |
| AC2 | `uv run --frozen --with pytest-cov python -m pytest -q --cov=chatpid --cov-report=xml:coverage.xml` locally; CI job `sonar` test step | local 241 passed, 3 skipped, `coverage.xml` written; CI (Linux) 242 passed, 2 skipped, `coverage.xml` written, `uv.lock` untouched |
| AC3 | Workflow YAML parsed with PyYAML (jobs and steps listed). Guard script extracted and run with `SONAR_TOKEN` empty, then set. CI `sonar` job on the PR. Deliberate break: added `--no-such-flag` to the test step (commit 844d310), pushed, then reverted | YAML parses. Empty token: notice `SonarCloud scan skipped`, exit 0, `enabled=false`. Token set: exit 0, `enabled=true`. Scan on the PR: log says `Failed to load settings with NOT_FOUND ... project does not exist yet`, then `ANALYSIS SUCCESSFUL`, dashboard `id=vishal7pandey_chatpid&pullRequest=24`, job green. Broken step: `sonarcloud` job red (fail, 41s), other checks green; restored: see PR checks (green) |
| AC4 | Public SonarCloud API after the merge | recorded on CPID-40 |
| AC5 | Scan log | no Automatic Analysis refusal; analysis uploaded and accepted |
