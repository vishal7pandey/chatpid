# CPID-1 — Clean up ruff lint/format debt, then enforce ruff in CI

Status: spec-approved · Risk: medium · Jira: CPID-1
Created: 2026-10-05 · Slug: ruff-debt

## Problem

`ruff check .` reports 84 errors and `ruff format --check .` would reformat 40 files, so CI could not enforce
ruff and `.github/workflows/ci.yml` runs only pytest. New lint and style regressions go in unnoticed, and every
later change that touches a file pays the formatting noise.

## Users and context

Engineers and agents changing `chatpid/`, `scripts/`, `tests/`. Grounded in: `pyproject.toml` (no ruff config
yet, ruff 0.16.3 locally), `.github/workflows/ci.yml`, `.factory/verify.py` (kit-managed, hash-tracked in
`.factory/factory.yaml`), and the 38 existing tests.

## Goals and non-goals

**Goals**
- `ruff check .` and `ruff format --check .` pass with zero errors.
- Both run in CI before pytest, so the `test` job fails on a regression.
- No behaviour change.

**Non-goals**
- No new lint rules beyond ruff's defaults; no type checking; no refactors for style.
- No edits to `.factory/` (kit-managed files must stay byte-identical).
- No new tests (CPID-16 covers tests).

## Requirements

- R1. Safe auto-fixable findings (unused imports/variables, unsorted imports, f-strings without placeholders, unnecessary key checks) are fixed in the code.
- R2. Non-auto-fixable findings are fixed by hand without changing behaviour, except where noted in the PR.
- R3. A rule ignore is allowed only with a written justification in `pyproject.toml`; `.factory/` is excluded from ruff because it is managed by the kit.
- R4. All files are formatted with `ruff format`.
- R5. `ci.yml` runs `uv run ruff check .` and `uv run ruff format --check .` before `uv run pytest -q`.

## Acceptance criteria

- AC1. (R1, R2, R3) `.venv/Scripts/python.exe -m ruff check .` prints `All checks passed!`.
- AC2. (R4) `.venv/Scripts/python.exe -m ruff format --check .` reports all files already formatted.
- AC3. (R1, R2, R4) `.venv/Scripts/python.exe -m pytest -q` still reports 38 passed, and every `chatpid.*` module imports.
- AC4. (R5) `.github/workflows/ci.yml` contains both ruff steps; on the PR the `test` check passes, proving they pass on Linux CI.
- AC5. (R3) `git diff main -- .factory` is empty, and `pyproject.toml` has a comment for each ignored rule (BLE001) and the `.factory` exclude.
- AC6. (failure path, R5) Running `ruff check` on a file with an unused import (scratch check, not committed) exits non-zero, proving the gate would fail.

## Edge cases and failure modes

- Ruff version drift: `uv.lock` is git-ignored so CI installs the newest `ruff>=0.6`; a newer ruff can add default rules and fail CI. Accepted, recorded as a risk.
- Hand-fixes in `chatpid/vector_rag.py` and `scripts/14_score_benchmark.py` must preserve results for normal inputs.

## Non-functional requirements

- CI change only adds steps; permissions stay `contents: read` (security.md).

## Assumptions

- Per-rule ignore of BLE001 is preferred over rewriting 31 deliberate `except Exception` boundaries (agent tool wrapper, CypherRAG fallback, benchmark loops, HTTP handlers).
- The ticket's own note favours relaxing rules for this experiment-style repo over polish.

## Risks and dependencies

Medium: touches 40 files and CI, though mechanically; a large formatting diff makes review hard and can conflict with open branches (hence done first). Revert is a single commit.
