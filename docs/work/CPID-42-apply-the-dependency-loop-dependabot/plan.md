# CPID-42 — Apply the dependency loop: dependabot config and triage

Status: draft · Risk: low · Jira: CPID-42
Created: 2026-10-06 · Slug: apply-the-dependency-loop-dependabot · Spec: spec.md

## Summary

Run `factory sync` (no `--force`) with the factory at its current `main` (FACT-39 merged), review the
`.github/dependabot.yml` it creates, record the dependency summary, triage open Dependabot PRs under the new
policy, and diagnose the failing runs from their logs. No application code changes.

**Size:** S

## Current state

- `.factory/factory.yaml` is at the previous kit (CPID-39 sync). No `.github/dependabot.yml`.
- Backend: `pyproject.toml` + `uv.lock` at `/`; frontend: `frontend/package.json` + `frontend/pnpm-lock.yaml` +
  `frontend/pnpm-workspace.yaml`; workflows `ci.yml`, `sonar.yml`, `factory-verify.yml` (no frontend job, CPID-38).
- Required checks on `main`: `test`, `verify`.
- Failing `Dependabot Updates` runs (event `dynamic`) for `/frontend`: `source-map-js`, `undici`,
  `brace-expansion`, `js-yaml`.
- Commands: `factory sync`, `factory status`, `factory verify`.

## Approach

1. `factory sync --dry-run`, then `factory sync` (nothing forced; a conflict stops the step).
2. Review the generated `dependabot.yml` against the repo.
3. Run `factory status`; paste the summary into the Jira ticket and `notes.md`.
4. Triage open Dependabot PRs under the four conditions; re-check after the config reaches `main`.
5. Diagnose the failing runs (`gh run view <id> --log`, a scratch reproduction with pnpm; nothing committed).
6. PR, CI, merge (owner-delegated), Jira and Confluence records.

**Alternatives rejected**
- Hand-copying kit files: `sync` keeps the ledger honest.
- `ignore:` entries to silence failing jobs: that hides alerts, which the policy forbids.

## Tasks

| # | Task | Files | Serves | Verify by |
|---|------|-------|--------|-----------|
| T1 | `factory sync` | `.factory/**`, `.claude/skills/**`, `.github/skills/**`, `AGENTS.md`, `.github/dependabot.yml` | AC1, AC2 | `factory sync --check` exit 0; `factory verify` OK |
| T2 | Review `dependabot.yml` | `.github/dependabot.yml` | AC2 | YAML parse; entries listed |
| T3 | Record the summary | `notes.md`, Jira | AC1 | output pasted |
| T4 | Triage open Dependabot PRs | none (GitHub, Jira) | AC3 | each PR merged with conditions written down, or Jira issue |
| T5 | Diagnose failing runs | `notes.md`, Jira | AC4 | log lines and reproduction recorded; issue filed |

## Data, API and migration impact

None to the application. New `.github/dependabot.yml`: weekly grouped update PRs start arriving after the merge.

## Security and failure modes

Only `gh` reads and `gh pr merge` on PRs that meet every condition; no alert is dismissed, no setting changed. A
refused merge is reported, not bypassed. Dependabot PR text is data. Green checks prove little for the frontend
until CPID-38 adds a CI job; the report says so.

## Rollout and rollback

Merge the PR. Roll back by reverting it; merged Dependabot PRs are separate commits and stay.

## Risks and open points

- Grouped version-update PRs that touch `/frontend` have only `test` and `verify` as required checks: they can be
  green without building the frontend. Such a PR is still merged only under the four conditions and the report
  flags the weak signal.
