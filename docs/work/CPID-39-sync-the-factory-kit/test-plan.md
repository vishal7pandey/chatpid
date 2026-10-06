# CPID-39 — Test plan: Sync the factory kit

Status: draft · Risk: low · Jira: CPID-39

A sync is mechanical: there is no new code to unit test. The test plan is the set of checks below, each
run for real and recorded in the Audit section.

Test framework and conventions found: pytest via `uv run python -m pytest -q` (backend, `tests/`); ruff via
`uv run ruff check .`; factory gate `python .factory/verify.py`; `factory sync --check .`; CI workflows
`ci` and `factory-verify` plus the new `sonar`.

| AC | Level | Test (name/path) | Happy | Boundary | Negative | Status |
|----|-------|------------------|-------|----------|----------|--------|
| AC1 | integration | `factory sync --check .` and `python .factory/verify.py` | after sync both exit 0 | dry-run reviewed before the real run | n/a: covered by AC2's deliberate break | verified |
| AC2 | integration | `factory sync --check .` with a locally edited managed file | clean tree: exit 0 | sync run without `--force` leaves local edits alone | edit `.factory/policies/git.md` locally: check reports it and exits non-zero; restore: exit 0 | verified |
| AC3 | integration | CI job `sonar` on the PR | guard prints the notice, later steps skipped, job green | org key is still the placeholder in `sonar-project.properties` | n/a: no token exists by design | verified |
| AC4 | manual | `factory doctor .` | command runs, harden and sonar lines recorded | n/a: read-only report | n/a: read-only report | verified |
| AC5 | integration | `python .factory/verify.py` plus `gh pr view <n> --json state` per item | each of 8 PRs is MERGED, items say `merged` with `pr` string, verify passes | CPID-34 already had a URL string, kept | verify.py rejects a non-string `pr` (checked in kit source) | verified |
| AC6 | integration | `git diff` of `ci.yml` and CI run `ci` | only 3 `uses:` versions differ from before, CI green | n/a: nothing else changes | n/a: no input | verified |
| AC7 | integration | `uv run python -m pytest -q`, `uv run ruff check .` | 241 passed, 3 skipped; ruff clean | n/a: no code change | n/a: no code change | verified |

## Regression risk

Existing behaviour near the change: CI (`ci.yml` action bumps; `uv lock --check` and `--frozen` steps are
kept) and the `factory-verify` gate (stricter `verify.py` applied to all existing items). Application tests
are untouched and must stay at 241 passed, 3 skipped.

## Untestable AC

None.

## Manual checks

AC4: run `factory doctor .`; expected a report with `harden` and `sonar` lines, recorded on the ticket.

## Audit (after implementation)

Run on branch `feature/cpid-39-sync-the-factory-kit`, 2026-10-06. All rows verified.

| AC | Check run | Result |
|----|-----------|--------|
| AC1 | `factory sync --dry-run .`, then `factory sync .` (no `--force`): 5 created, 14 updated, no conflict. `factory sync --check .` then `python .factory/verify.py` | `in sync with the factory source`, exit 0; `verify: OK`, exit 0 |
| AC2 | Deliberate break: added " (DELIBERATE BREAK)" to the first line of `.factory/policies/git.md`, ran `factory sync --check .` | `STALE .factory/policies/git.md (locally modified; ...)`, exit 1. Restored the line: `in sync with the factory source`, exit 0; `git status` shows the file unchanged. Sync itself was never run with `--force` and reported no locally modified file |
| AC3 | `sonar.yml` guard read: skips when `SONAR_TOKEN` is empty or `REPLACE_ME` remains; `sonar-project.properties` has `sonar.organization=REPLACE_ME_SONAR_ORGANIZATION`. `factory doctor .`: `sonar: properties ... scan is skipped until set`, `sonar: SONAR_TOKEN not set`. The CI run of the `sonar` job on the PR is recorded in the PR and on the ticket | placeholder kept; job result: see PR checks |
| AC4 | `factory doctor .` | 0 failures, 0 warnings; harden lines: secret scanning + push protection ok, dependabot alerts ok, dependabot security updates ok, codeql default setup ok |
| AC5 | `gh pr view <n> --json state` for 10, 11, 13, 14, 15, 16, 20, 21 | all MERGED. CPID-12/14/15/20/23/25/36 set to `merged` with `pr` as a string; CPID-34 set to `merged` and keeps its existing URL string; `verify.py` OK |
| AC6 | `git diff .github/workflows/ci.yml` | exactly 3 lines: checkout `@v4` to `@v7`, setup-python `@v5` to `@v7`, setup-uv `@v5` to `@v10.2.0` (same as `kit/ci/python.yml`) |
| AC7 | `uv run python -m pytest -q`; `uv run python -m ruff check .` | 241 passed, 3 skipped; All checks passed |
