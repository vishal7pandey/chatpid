# CPID-23 — Plan: commit the lockfile, freeze CI

Status: plan-approved · Risk: low · Jira: CPID-23
Created: 2026-10-05 · Slug: commit-uv-lock · Spec: spec.md

## Summary

Un-ignore and commit `uv.lock`, add `uv lock --check` and `--frozen` to CI, update AGENTS.md.

**Size:** S

## Current state

`.gitignore` line `uv.lock`; `.github/workflows/ci.yml` runs `uv sync --all-extras --all-groups`; a local lock (138 packages, ruff 0.16.3) exists and `uv lock --check` passes against `pyproject.toml`.

## Approach

Delete the ignore line, `git add uv.lock`, edit the two CI lines, edit one AGENTS.md sentence.

**Alternatives rejected:** `--locked` on sync only (works, but the owner asked for `--frozen`; a separate `lock --check` keeps both properties).

## Tasks

| # | Task | Files | Serves | Verify by |
|---|------|-------|--------|-----------|
| T1 | Un-ignore and commit the lock | .gitignore, uv.lock | AC1 | `git ls-files uv.lock`, `uv lock --check` |
| T2 | CI lock check + frozen sync | .github/workflows/ci.yml | AC2, AC3 | CI `test` green; scratch stale-lock failure |
| T3 | Docs | AGENTS.md | AC4, AC5 | read |

## Data, API and migration impact

None.

## Security and failure modes

Pinned, reviewable dependencies are a security gain (security.md: lockfile committed). No dependency changes, so no audit needed.

## Rollout and rollback

Merge; revert to undo.

## Risks and open points

The Docker image still resolves unpinned (out of scope, flagged to the owner).
