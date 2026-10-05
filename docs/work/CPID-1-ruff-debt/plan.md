# CPID-1 — Plan: ruff debt

Status: plan-approved · Risk: medium · Jira: CPID-1
Created: 2026-10-05 · Slug: ruff-debt · Spec: spec.md

## Summary

Add a small `[tool.ruff]` config, apply `ruff check --fix` (safe fixes only), hand-fix the remaining findings,
run `ruff format`, then add the two ruff steps to `ci.yml`.

**Size:** S

## Current state

No ruff config in `pyproject.toml`; `ruff>=0.6` is in the `dev` extra. Findings (ruff 0.16.3): 31 BLE001, 17 F541,
15 I001, 11 F401, 2 F841, 2 RUF015, 2 RUF019, plus one each of PLW1510, S110, SIM115, TRY004. The last two of
those live in `.factory/verify.py`. Commands: `python -m ruff check .`, `python -m ruff format --check .`,
`python -m pytest -q`.

## Approach

1. pyproject: `extend-exclude = [".factory"]` and `ignore = ["BLE001"]`, each with a comment.
2. `ruff check . --fix` (safe fixes), review removed imports.
3. Hand fixes: `chatpid/vector_rag.py` (drop unused `embedding_prop`; label lookup via `next(..., "")`),
   `scripts/14_score_benchmark.py` (context manager, specific `except (OSError, ValueError)`),
   `scripts/22_platform_integration.py` (`next(iter(...))`), `scripts/25_ingest_real_dexpi.py` (unused variable).
4. `ruff format .`; add CI steps.

**Alternatives rejected**
- Narrow every `except Exception`: needs exception types of several SDKs; changes failure behaviour.
- Edit `.factory/verify.py` to satisfy ruff: kit-managed and hash-tracked; excluded instead.

## Tasks

| # | Task | Files | Serves | Verify by |
|---|------|-------|--------|-----------|
| T1 | ruff config in pyproject | pyproject.toml | AC5 | file content |
| T2 | auto-fix + hand-fix findings | chatpid/, scripts/, tests/ | AC1, AC3 | `ruff check .` clean, pytest 38 |
| T3 | format all files | whole repo | AC2 | `ruff format --check .` |
| T4 | CI steps | .github/workflows/ci.yml | AC4, AC6 | PR `test` check green; scratch unused-import check fails |

## Data, API and migration impact

None. One behaviour edge: `vector_rag` returns label `""` instead of raising IndexError when a node has only the `Node` label.

## Security and failure modes

CI change adds steps only. No dependency change.

## Rollout and rollback

Merge; revert the commit to undo (CI then only runs pytest again).

## Risks and open points

- Newer ruff than local may add default rules; signal is a red `test` job on an unrelated PR.
