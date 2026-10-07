# CPID-44 — Test plan: Adopt decision gate and charter

Status: draft · Risk: low · Jira: CPID-44

No application code changes, so there is nothing new to unit test. The tests are the factory's own validators and the
repo's regression checks, each run for real and recorded in the Audit section.

Test framework and conventions found: pytest via `uv run python -m pytest -q` (backend, `tests/`); ruff via
`uv run python -m ruff check .`; factory gate `python .factory/verify.py`; `factory sync --check .`;
`factory status`; `factory doctor .`; CI workflows `ci`, `factory-verify`, `sonar` and CodeQL.

| AC | Level | Test (name/path) | Happy | Boundary | Negative | Status |
|----|-------|------------------|-------|----------|----------|--------|
| AC1 | integration | `factory sync --check .`, `python .factory/verify.py` | after sync both exit 0 | dry run reviewed first; no `--force` | edit `.factory/policies/git.md`: check exits non-zero; restore: 0 | verified |
| AC2 | integration | `python .factory/verify.py` over `docs/decisions/` | D-001 is a valid proposed dismissal | exactly one recommended option | n/a: the validator's own tests cover bad records | verified |
| AC3 | integration | charter state via the factory's `charter.charter_state` and `factory doctor .` | `unapproved: decision D-002 is waiting for the owner` | 3 to 7 criteria, one reference each | a draft with a vague word would be `invalid`; checked that the state is not `invalid` or `template` | verified |
| AC4 | manual | `factory status`, `factory doctor .` | both records listed as waiting for the owner | n/a: read-only | n/a: read-only | verified |
| AC5 | manual | read of the charter against Jira | each named key exists; bar named with its source | n/a | n/a | verified |
| AC6 | manual | Jira JQL `labels = parked` and status of each | labelled, comment present, status unchanged | n/a | no ticket outside the parked list is labelled | verified |
| AC7 | integration | `uv run python -m pytest -q`, `uv run python -m ruff check .` | 262 passed, 3 skipped; ruff clean | n/a | n/a | verified |
| AC8 | manual | `grep -n "status:" docs/decisions/*.md`; `git diff` for `by:`/`at:` | both `proposed`, `by: null`, `at: null` | n/a | n/a | verified |

## Regression risk

The stricter synced `verify.py` is applied to all existing items and now also checks decisions and the charter; any
finding is fixed in the data, not by weakening the gate. Application tests are untouched and must stay at 262 passed,
3 skipped.

## Untestable AC

None.

## Manual checks

AC4: run `factory status` and `factory doctor .` and read both lists. AC5, AC6: read the charter and query Jira.

## Audit (after implementation)

Run on branch `feature/cpid-44-adopt-decision-gate-and-charter`, 2026-10-07. All rows verified.

| AC | Check run | Result |
|----|-----------|--------|
| AC1 | `factory sync --dry-run .` (2 create, 15 update, no conflict), then `factory sync .` without `--force`, then `factory sync --check .` and `python .factory/verify.py`. Deliberate break: appended a line to `.factory/policies/git.md`, ran `factory sync --check .`, restored the file from a copy | `in sync with the factory source`, exit 0; `verify: OK`. Break: `STALE .factory/policies/git.md (locally modified; ...)`, exit 1; after restore: exit 0, `git status` shows the file unchanged |
| AC2 | `python .factory/verify.py` with D-001 present; read of the record | `verify: OK`; D-001 is `dismissal`, `reason: false positive`, `jira: CPID-41`, two options, one recommended, `proposed` |
| AC3 | `charter.charter_state('.')` through the factory source | `unapproved - decision D-002 is waiting for the owner` (not `invalid`, not `template`) |
| AC4 | `factory status`, `factory doctor .` | status: `waiting for the owner (2 decisions)` D-001 and D-002; doctor: `WARN decision D-001`, `WARN decision D-002`, `WARN charter no approved charter: decision D-002 is waiting for the owner`, `0 failure(s), 5 warning(s)` (the other two warnings are the 10 failed Dependabot update runs, unrelated) |
| AC5 | Read of `docs/PROJECT.md`; Jira keys CPID-45, 27, 38, 41 looked up | five criteria, one reference each; all keys exist; C2 names the 0.7 bar, the 14 of 19 source and says it is the owner's to change |
| AC6 | Jira edit of labels on CPID-10, 11, 17, 18, 19, 22, 26, comment on each | label `parked` present on each; status unchanged (To Do, CPID-10 In Progress) |
| AC7 | `uv run python -m pytest -q`; `uv run python -m ruff check .` | 262 passed, 3 skipped; All checks passed |
| AC8 | read of both records and the charter | `status: proposed`, `decision: null`, `by: null`, `at: null`; `factory decide` was never run |
