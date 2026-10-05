# CPID-23 — Commit uv.lock and make CI install with uv sync --frozen

Status: spec-approved · Risk: low · Jira: CPID-23
Created: 2026-10-05 · Slug: commit-uv-lock

## Problem

`uv.lock` is git-ignored, so CI resolves dependencies fresh on every run. A new ruff or pytest release can turn main red with no change from us (the CPID-1 ruff gate is the exposed one), and nobody can reproduce a CI result locally. Owner decision (delegated, 2026-10-05): commit the lock.

## Goals and non-goals

**Goals:** a tracked `uv.lock`; CI installs exactly what it pins; a stale lock fails CI.
**Non-goals:** no dependency changes or upgrades; no Dockerfile change (`Dockerfile.api` runs `uv sync --no-dev` without the lock and does not copy it; changing the image build is a deploy decision, noted for the owner).

## Requirements

- R1. `uv.lock` is committed and no longer ignored; it is in sync with `pyproject.toml`.
- R2. CI runs `uv lock --check` (fails when the lock is stale) and installs with `uv sync --frozen --all-extras --all-groups`.
- R3. AGENTS.md describes the committed lock.
- R4. The ruff version the lock pins is recorded: ruff 0.16.3.

## Acceptance criteria

- AC1. (R1) `git ls-files uv.lock` lists it, `git check-ignore uv.lock` prints nothing, and `uv lock --check` succeeds on the branch.
- AC2. (R2) `.github/workflows/ci.yml` contains both steps before ruff and pytest; on the PR the `test` check passes on Linux with them.
- AC3. (R2, failure path) With a scratch edit of `pyproject.toml` (`ruff>=0.16.4`), `uv lock --check` fails with "needs to be updated" (done locally, edit reverted, not committed).
- AC4. (R3) AGENTS.md no longer says the lock is git-ignored.
- AC5. (R4) The ruff version is stated here and in the Jira ticket.

## Edge cases and failure modes

- The lock was generated on Windows with Python 3.14; it is a universal lockfile (`requires-python >=3.12`, resolution markers), and `uv lock --check` plus the Linux CI run prove it works for 3.12 on Linux.
- `--frozen` alone does not detect a stale lock, hence the separate `uv lock --check` step.
- Contributors who change dependencies must run `uv lock` and commit the result.

## Risks

Low. CI configuration change (owner-authorised). Rollback: revert the commit.
