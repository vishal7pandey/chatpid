# CPID-23 — Test plan: commit uv.lock

Status: implementing · Risk: low · Jira: CPID-23

Test framework and conventions found: no unit tests apply to a lockfile or CI config; proof is command output and the CI run. Project tests `.venv/Scripts/python.exe -m pytest -q` must stay green.

| AC | Level | Test (name/path) | Happy | Boundary | Negative | Status |
|----|-------|------------------|-------|----------|----------|--------|
| AC1 | manual | `git ls-files uv.lock`; `git check-ignore uv.lock`; `uv lock --check` | lock tracked, check passes | n/a: single file | n/a: see AC3 | verified |
| AC2 | e2e | CI `test` job on the PR (`uv lock --check`, `uv sync --frozen ...`, ruff, pytest on Linux/3.12) | job green | n/a: single job | n/a: see AC3 | verified |
| AC3 | manual | scratch `pyproject.toml` edit then `uv lock --check` | n/a: negative-only | n/a: single case | stale lock -> "needs to be updated", non-zero | verified |
| AC4 | manual | read AGENTS.md | sentence replaced | n/a: single edit | n/a: no negative path | verified |
| AC5 | manual | read spec and Jira ticket | ruff 0.16.3 recorded | n/a: single fact | n/a: no negative path | verified |

## Regression risk

CI could fail if the lock lacks the `[dev]` extra or a platform wheel; the PR run answers that. Project tests are untouched.

## Untestable AC

None.

## Manual checks

Level manual rows above: run the quoted commands in the repo root; expected output as in the Happy / Negative column.

## Audit (after implementation)

AC3 mutation: changed `ruff>=0.6` to `ruff>=0.16.4` in `pyproject.toml`; `uv lock --check` printed "The lockfile at `uv.lock` needs to be updated" and exited non-zero; the edit was reverted and `uv lock --check` passed again. AC2: the PR `test` check is the proof for Linux.
