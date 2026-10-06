# CPID-39 — Sync the factory kit

Status: draft · Risk: low · Jira: CPID-39
Created: 2026-10-06 · Slug: sync-the-factory-kit

## Problem

ChatPID adopted the factory kit on 2026-10-04 (CPID-3). The kit has moved on since: new skill and policy
for findings (`factory-findings`, `findings.md`), a stricter `verify.py`, delegated-approval rules,
merged-status handling, file-editing hazards in `factory-implement`, and a SonarCloud workflow and
properties template. Until this repo syncs, its agents follow outdated rules and CI runs the old gate.
Several work items are also stale: they say `in-review` although their pull requests were merged days ago.

## Users and context

The repo owner and the agents working in this repo. Touches only factory-managed files (`.factory/`,
`.claude/skills/factory-*`, `.github/skills/factory-*`, the `AGENTS.md` factory block,
`.github/workflows/factory-verify.yml`), two new dormant SonarCloud files, `docs/work/*/item.yaml` status
fields, and action versions in the user-owned `.github/workflows/ci.yml`. Grounded in the output of
`factory sync --dry-run .` and the kit at `C:\Dev\ai-software-factory\kit\`.

## Goals and non-goals

**Goals**
- Bring every factory-managed file to the current kit version without overwriting local edits.
- Add the SonarCloud workflow and properties file in their dormant state.
- Bring work-item state in line with reality (merged PRs recorded as merged).
- Move the CI action versions in `ci.yml` to Node 24 capable releases (FACT-15).

**Non-goals**
- No change to application code, tests, dependencies or the frontend.
- No SonarCloud organisation key and no `SONAR_TOKEN`: the owner supplies both later; nothing is invented.
- No other change to `ci.yml` than action versions (it is user-owned; its extra `uv lock --check` and
  `--frozen` steps stay).
- No `--force` sync.

## Requirements

- R1. The sync must apply the planned kit changes without `--force`; a locally modified managed file must
  not be overwritten.
- R2. The new Sonar workflow must stay dormant: with no org key and no token it prints a notice and skips
  the scan steps, and the job passes.
- R3. `sonar-project.properties` must keep the organisation placeholder.
- R4. Work items whose pull request is merged must record status `merged` and the PR number as a string.
- R5. `ci.yml` action versions must match the current kit CI template versions; nothing else in it changes.
- R6. The post-sync state must be checked and recorded: `sync --check`, `verify.py`, `doctor`, backend tests.

## Acceptance criteria

- AC1. `factory sync --dry-run .` is reviewed first; after `factory sync .`, `factory sync --check .` exits 0
  and `python .factory/verify.py` passes. (R1, R6)
- AC2. No locally modified managed file is overwritten (no `--force`). If sync reports one, work stops and
  the conflict is reported on CPID-39. As a failure-path check, a deliberate local edit to a managed file
  makes `sync --check` report it (non-zero), and restoring the file makes it exit 0 again. (R1)
- AC3. The `sonar` job is green on the PR in its dormant state (notice printed, later steps skipped), and
  `sonar-project.properties` still holds the organisation placeholder. (R2, R3)
- AC4. `factory doctor .` runs and its `harden` and `sonar` lines are recorded on the ticket. (R6)
- AC5. Every `docs/work/*/item.yaml` that was `in-review` with a merged PR is `merged` with `pr` a string
  (CPID-12, 14, 15, 20, 23, 25, 34, 36); `verify.py` still passes. (R4)
- AC6. In `ci.yml` only the `uses:` versions of checkout, setup-python and setup-uv change, to the kit
  template's versions; the CI run on the PR is green. (R5)
- AC7. Backend baseline is unchanged: 241 passed, 3 skipped, `ruff check` clean. (R6)

## Edge cases and failure modes

- A managed file with local edits: sync skips it and reports it; stop and report on the ticket (AC2).
- A merged PR whose number cannot be found: leave the item as is and say so on the ticket.
- Sonar guard when the org key is the placeholder: job must exit 0, not fail (AC3).
- A kit action version that does not exist as a tag: CI fails on the PR; fix before merge.

## Non-functional requirements

- Security (`.factory/policies/security.md`): no secret is read, written or printed; `.env` untouched;
  `SONAR_TOKEN` is neither created nor referenced beyond the template's own guard.
- Reversible: one revert of the merge commit restores the previous state.

## Assumptions

- The PR number as a string (`pr: "20"`) is the recorded form for merged items (FACT-20 convention).
- Items already `done` keep their existing URL form; only the in-review ones listed are changed.
- The Node 24 capable versions are the ones in the kit's current CI template.

## Risks and dependencies

- Low risk: configuration and process files only, easily reverted. The newer `verify.py` is stricter and may
  flag existing items; any such finding is fixed in the item metadata, not by weakening the gate.
- Dependency on the owner for the SonarCloud org key and token (out of scope here).

## Open questions

None.
