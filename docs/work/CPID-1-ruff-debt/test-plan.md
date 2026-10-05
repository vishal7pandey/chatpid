# CPID-1 — Test plan: ruff debt

Status: plan-approved · Risk: medium · Jira: CPID-1

Test framework and conventions found: pytest in `tests/`, run with `.venv/Scripts/python.exe -m pytest -q` (38 tests).
The lint/format criteria are verified by running ruff itself; the gate is the CI job.

| AC | Level | Test (name/path) | Happy | Boundary | Negative | Status |
|----|-------|------------------|-------|----------|----------|--------|
| AC1 | integration | `python -m ruff check .` | prints All checks passed | n/a: whole repo | see AC6 | verified |
| AC2 | integration | `python -m ruff format --check .` | 74 files already formatted | n/a: whole repo | n/a: no input | verified |
| AC3 | unit | existing tests/ (38) plus import of each chatpid module | 38 passed, imports succeed | n/a: unchanged tests | n/a: no new behaviour | verified |
| AC4 | integration | PR check `test` on GitHub (ci.yml) | job green with both ruff steps | n/a: single job | n/a: see AC6 | verified |
| AC5 | manual | `git diff main -- .factory` and read pyproject.toml | empty diff; comments present | n/a: static | n/a: no input | verified |
| AC6 | manual | scratch file with `import os` unused, `ruff check` | exits 1 | n/a: single file | the unused import is the failing input | verified |

## Regression risk

Hand-fixed code: `chatpid/vector_rag.py` (label extraction), `scripts/14_score_benchmark.py` (latest-file finder),
`scripts/22_platform_integration.py`, `scripts/25_ingest_real_dexpi.py`. None have tests today (CPID-16 adds vector_rag
tests); import checks and compileall cover syntax. Existing 38 tests must stay green.

## Untestable AC

None.

## Manual checks

AC5 and AC6: run the commands in the table and observe the stated result.

## Audit (after implementation)

AC6 audited with a scratch file under the scratchpad (not committed): ruff check exited 1 with F401.
