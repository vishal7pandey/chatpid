# CPID-40 — Enable SonarCloud

Status: draft · Risk: low · Jira: CPID-40
Created: 2026-10-06 · Slug: enable-sonarcloud

## Problem

CPID-39 synced the factory kit's SonarCloud workflow (`.github/workflows/sonar.yml`) and
`sonar-project.properties`, but both were dormant: the organisation key was a placeholder and no token
existed. On 2026-10-06 the owner supplied the organisation key and a token (validated against the
SonarCloud API: organisation found, 0 projects) and `SONAR_TOKEN` is now a GitHub Actions secret on this
repo. The kit's test step is a generic default that does not match how this project runs its tests
(`ci.yml`: Python 3.12, `uv sync --frozen --all-extras --all-groups`, `uv run pytest -q`), so the first real
scan would run a different install and test command than CI and could fail or report wrong coverage.

## Users and context

The repo owner and agents working here. Touches `sonar-project.properties` (organisation key already set in
the working tree), `.github/workflows/sonar.yml`, and the work item. Grounded in `ci.yml`, `pyproject.toml`
(`pytest` and `ruff` live in the `[dev]` extra; `pytest-cov` is not a dependency), `AGENTS.md`, and the
SonarCloud API. The frontend (`frontend/`, Next.js) has no CI yet (CPID-38).

## Goals and non-goals

**Goals**
- The `sonar` job scans this project on PRs and on pushes to `main` and creates the project in the
  organisation on its first analysis.
- The backend tests in that job run the way `ci.yml` runs them, and produce `coverage.xml` where
  `sonar-project.properties` expects it.

**Non-goals**
- No frontend analysis tuning and no frontend CI (CPID-38). Frontend files stay in the default scan scope;
  exclusions are added only if the scan needs them.
- No new project dependency (`pytest-cov` is added for the Sonar run only) and no `uv.lock` change.
- No quality-gate enforcement (`sonar.qualitygate.wait`); no fixing of the issues Sonar reports.
- No change to `ci.yml`.

## Requirements

- R1. `sonar-project.properties` must hold the real organisation key and `sonar.projectKey=vishal7pandey_chatpid`.
- R2. The `sonar` job must install and test exactly as `ci.yml` does (Python 3.12, `uv sync --frozen
  --all-extras --all-groups`, `uv run pytest -q`), with coverage added, writing `coverage.xml`.
- R3. `sonar.python.version` must equal the CI Python version (3.12).
- R4. The guard must keep skipping the scan, with a notice and a green job, when `SONAR_TOKEN` is empty
  or a `REPLACE_ME` value remains.
- R5. After merge the project must exist in the SonarCloud organisation with a first analysis whose
  quality gate status and issue count are recorded on the ticket.
- R6. Automatic Analysis must be off for the project; if it is on, the owner is told (UI-only setting).

## Acceptance criteria

- AC1. `sonar-project.properties` has the real `sonar.organization` (no `REPLACE_ME`) and
  `sonar.projectKey=vishal7pandey_chatpid`; `sonar.python.version=3.12`. (R1, R3)
- AC2. In `sonar.yml` the install step is `uv sync --frozen --all-extras --all-groups` and the test step
  runs `uv run ... pytest -q` with coverage, writing `coverage.xml`; run locally the command gives
  241 passed, 3 skipped and a `coverage.xml`, and the `sonar` job's test step passes in CI. (R2)
- AC3. On the PR the guard no longer skips and a scan runs. If SonarCloud rejects the project key or needs
  the project imported first, the exact reason is recorded on the ticket. Failure path: with the token
  empty the guard still prints the skip notice and the job exits 0 (simulated by running the guard script
  with `SONAR_TOKEN` unset), and a deliberately broken test step turns the job red until restored. (R2, R4)
- AC4. After merge, the project `vishal7pandey_chatpid` exists in the organisation (read through the public
  SonarCloud API, count 0 to 1 or more); its first analysis, quality gate status and issue count are
  recorded on CPID-40. (R5)
- AC5. Automatic Analysis is off for the project; if the scan is refused because it is on, the owner is
  told and the ticket stays In Progress. (R6)

## Edge cases and failure modes

- Fork or Dependabot PRs have no secret: the job's `if:` and the guard skip them (unchanged).
- The project does not exist yet: the first analysis with a token that may create projects creates it; if
  SonarCloud refuses (key, import needed, Automatic Analysis on), record the exact job-log reason and stop.
- A flaky or failing backend test: the job fails before the scan, as in `ci`; fix the test, not the gate.
- `pytest-cov` cannot be fetched: the test step fails visibly, no silent skip.

## Non-functional requirements

- Security (`.factory/policies/security.md`): the token is read only through the `secrets` context; never
  printed; `.env` not opened. The organisation key is not a secret.
- Reversible: one revert of the merge commit restores the dormant state.

## Assumptions

- `pytest-cov` is added with `uv run --with` (run-only) rather than to the `[dev]` extra, to avoid a
  dependency and lock change; the owner can overrule at approval.
- Coverage is measured on the `chatpid` package (`--cov=chatpid`), not on `scripts/` or `tests/`.
- Frontend sources stay in the default scan scope; `node_modules` is already excluded and `.next` is
  git-ignored so it is absent from the CI checkout.
- Binary pickles under `data/` (`**/*.pkl`) are excluded: the first scan tried to read them as UTF-8 text and
  logged one encoding warning per file. This is the only exclusion the scan needed.

## Risks and dependencies

- Low risk: CI configuration only, easily reverted. Depends on the owner's token being able to create
  projects in the organisation and on Automatic Analysis being off.

## Open questions

None.
