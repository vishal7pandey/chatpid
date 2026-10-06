# CPID-40 — Enable SonarCloud

Status: draft · Risk: low · Jira: CPID-40
Created: 2026-10-06 · Slug: enable-sonarcloud · Spec: spec.md

## Summary

Keep the real organisation key already set in `sonar-project.properties`, and align the Sonar job's install
and test steps with `ci.yml` so the first scan analyses a tested tree with real coverage. Verify on the PR
(scan runs), then after merge through the public SonarCloud API.

**Size:** S

## Current state

- `sonar-project.properties`: `sonar.organization=vishal7pandey` (uncommitted, set by the owner's agent),
  `sonar.projectKey=vishal7pandey_chatpid`, `sonar.python.version=3.12`,
  `sonar.python.coverage.reportPaths=coverage.xml`, exclusions for `.venv`, `node_modules`, caches.
- `.github/workflows/sonar.yml` (kit default): `uv sync --all-extras --all-groups` (not frozen) and
  `uv run --with pytest-cov python -m pytest -q --cov --cov-report=xml:coverage.xml`.
- `.github/workflows/ci.yml`: Python 3.12, `uv lock --check`, `uv sync --frozen --all-extras --all-groups`,
  ruff check/format, `uv run pytest -q`.
- `pyproject.toml`: pytest and ruff in the `[dev]` extra; no pytest-cov. Baseline 241 passed, 3 skipped.

## Approach

Smallest change: make the install frozen like CI, and run `uv run --frozen --with pytest-cov pytest -q
--cov=chatpid --cov-report=xml:coverage.xml` (same command as CI plus coverage, run-only plugin, lock
untouched). The guard, triggers, permissions and the scan step stay as they are.

**Alternatives rejected**
- Add `pytest-cov` to the `[dev]` extra — changes dependencies and `uv.lock`, needs approval; `--with` avoids it.
- Bare `--cov` — measures whatever is imported incl. tests; `--cov=chatpid` measures the product code.
- Frontend exclusions or analysis now — frontend has no CI (CPID-38); out of scope.

## Tasks

| # | Task | Files | Serves | Verify by |
|---|------|-------|--------|-----------|
| T1 | Keep org key; confirm key, project key and python version | `sonar-project.properties` | AC1 | file read: no `REPLACE_ME`, `sonar.python.version=3.12` |
| T2 | Frozen install and CI-equivalent test command with coverage | `.github/workflows/sonar.yml` | AC2 | local run: 241 passed, 3 skipped, `coverage.xml` exists; YAML parses |
| T3 | Guard checks: simulate empty token; deliberate break of the test step | `sonar.yml` (temporary) | AC3 | guard exits 0 with notice; broken step shows red, restored shows green |
| T4 | PR; watch checks; read the `sonar` job log if it fails | none | AC3, AC5 | `gh pr checks --watch` all green, scan step ran |
| T5 | Merge; read the public SonarCloud API for project, gate, issues | none | AC4 | project count >= 1, gate status and issue count printed |
| T6 | Record on Jira and Confluence change log | none | AC4, AC5 | comments and page row present |

## Data, API and migration impact

None. No application code, dependency or lock change. Creates the SonarCloud project on first analysis.

## Security and failure modes

`SONAR_TOKEN` is only referenced through `secrets` in the existing steps; not printed. `.env` untouched. If
SonarCloud refuses the scan (wrong key, project must be imported, Automatic Analysis on) the job goes red on
the PR; the log reason is recorded and, if it needs the owner, work stops with the ticket In Progress.

## Rollout and rollback

Merge the PR; the push to `main` runs the first analysis. Rollback: revert the merge commit (the SonarCloud
project would remain; the owner can delete it in the UI). No point of no return.

## Risks and open points

- The token may lack permission to create projects: the log will say so.
- Automatic Analysis on for a new project blocks CI analysis: owner action in the UI.
