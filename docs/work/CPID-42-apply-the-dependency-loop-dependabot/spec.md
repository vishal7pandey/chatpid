# CPID-42 — Apply the dependency loop: dependabot config and triage

Status: draft · Risk: low · Jira: CPID-42
Created: 2026-10-06 · Slug: apply-the-dependency-loop-dependabot

## Problem

The factory now ships a dependency loop (factory ticket FACT-39: policy `dependencies.md`, skill
`factory-dependencies`, a `dependabot.yml` template, a dependency summary in `factory status`). chatpid has none of
it: no `.github/dependabot.yml`, no rule for when an agent may merge a Dependabot PR, and nothing that shows open
alerts, open Dependabot PRs and failed `Dependabot Updates` runs. Ten such runs failed in the last 7 days
(`npm_and_yarn in /frontend`). The frontend has no CI job (CPID-38), so a green Dependabot PR proves little for it.

## Users and context

The owner and the coding agent working in this repo (Python backend with `uv`, frontend with `pnpm` in `/frontend`,
GitHub Actions). Grounded in `.factory/policies/dependencies.md` (after sync), the failing runs' logs and
`frontend/package.json`, `frontend/pnpm-lock.yaml`, `frontend/pnpm-workspace.yaml`.

## Goals and non-goals

**Goals**
- The new policy, skill and AGENTS block arrive through `factory sync` (no `--force`).
- `.github/dependabot.yml` for the ecosystems chatpid uses.
- The dependency summary printed and recorded; every open Dependabot PR merged under the policy or filed.
- Any failing `Dependabot Updates` run diagnosed and its cause recorded.

**Non-goals**
- Other findings: no alert is filed, fixed or dismissed here. SonarCloud, CPID-38 (frontend CI job), CPID-41.

## Requirements

- R1. `factory sync` lays in the policy, skills and AGENTS block, leaving locally modified managed files alone.
- R2. `.github/dependabot.yml` has entries for `uv` at `/`, `npm` at `/frontend` (pnpm lockfile) and
  `github-actions` at `/`, weekly, grouped minor and patch.
- R3. The output of `factory status` (dependency summary) is recorded on CPID-42 and in `notes.md`.
- R4. Each open Dependabot PR is triaged against the four conditions of the policy: merged when all hold, else a
  Jira issue states the failed condition and the PR stays open. The report says where green checks prove little
  (the frontend, CPID-38).
- R5. The failing runs are diagnosed from their logs; the cause is recorded, a configuration cause is fixed,
  otherwise an issue is filed.

## Acceptance criteria

- AC1. (R1, R3) After sync, `factory sync --check` is clean and `factory status` prints the dependency summary;
  its output is on the Jira ticket and in `notes.md`.
- AC2. (R2) `.github/dependabot.yml` parses and lists exactly `uv /`, `npm /frontend`, `github-actions /`, each
  weekly with a `minor-and-patch` group.
- AC3. (R4) Every Dependabot PR open at triage time is either merged (all four conditions checked and written down)
  or has a Jira issue naming the failed condition; none is merged that fails a condition.
- AC4. (R5) The cause of the failing runs is stated with evidence (log lines, reproduction), with a fix merged or an
  issue filed.
