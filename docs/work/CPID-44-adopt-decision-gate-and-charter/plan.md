# CPID-44 — Adopt decision gate and charter

Status: draft · Risk: low · Jira: CPID-44
Created: 2026-10-07 · Slug: adopt-decision-gate-and-charter · Spec: spec.md

## Summary

Sync the kit with the factory CLI (no `--force`), scaffold the two decision records with `factory decision new`, fill
them and the charter from facts already in the repo and Jira, label the parked tickets, and verify with the
factory's own checks. Nothing is accepted: both records stay `proposed` for the owner.

**Size:** S

## Current state

- `factory sync --dry-run .` plans 2 creates (`docs/decisions/TEMPLATE.md`, `docs/PROJECT.md` as a template) and 15
  updates (AGENTS.md block, `.factory/verify.py`, `factory.yaml`, policies `autonomy.md` and `findings.md`, skills
  `factory-diagnose`, `findings`, `plan`, `spec`, `workflow` in both skill dirs).
- No `docs/decisions/` yet. CPID-41 (status In Progress, work item merged as PR #25, #26 follow-up) carries the
  agent's dismissal proposal as a Jira comment.
- Open CPID tickets (To Do or In Progress): 10, 11, 17, 18, 19, 21, 22, 26, 27, 38, 41, plus this item and the two new
  tickets 45 and 46.
- Checks: `uv run python -m pytest -q` (262 passed, 3 skipped), `uv run python -m ruff check .`,
  `python .factory/verify.py`.

## Approach

1. Sync (dry run, then real, no `--force`), then check.
2. `factory decision new` for the dismissal (type `dismissal`, `--alert`, `--reason "false positive"`, `--jira CPID-41`);
   write Context, Evidence, Options, Recommendation from the spec of CPID-41 and the tests that prove it.
3. Replace the template `docs/PROJECT.md` with the real charter; `factory decision new --type charter` creates the
   record, then name it in the charter's `decision:`.
4. Choose a reference per criterion that works offline: C1 `jira: CPID-45`, C2 `metric` on
   `docs/eval/benchmark-latest.json`, C3 `jira: CPID-27`, C4 `jira: CPID-38`, C5 `jira: CPID-41`.
5. Add the `parked` label and comment to the open tickets the criteria do not need (Jira only).
6. Run `factory status`, `factory doctor .`, the charter state, verify, backend checks.

**Alternatives rejected**
- `work` references for C1 to C4: the work items do not exist yet and would have to be invented.
- A `file` reference for the benchmark: existence of a file says nothing about the score; a `metric` does.
- Accepting the records with a delegated answer: refused by the factory for charter and dismissal, and by the owner.

## Tasks

| # | Task | Files | Serves | Verify by |
|---|------|-------|--------|-----------|
| T1 | Review `sync --dry-run .`, run `sync .` without `--force` | managed files | AC1 | `sync --check .` exit 0 |
| T2 | Deliberate break: edit a managed file, check, restore | one managed file (temporary) | AC1 | check non-zero, then 0 |
| T3 | Dismissal record for CPID-41 | `docs/decisions/D-001-*.md` | AC2 | verify OK; `factory status` lists it |
| T4 | Charter and charter record | `docs/PROJECT.md`, `docs/decisions/D-002-*.md` | AC3, AC5 | charter state "waiting for the owner" |
| T5 | Label parked tickets, comment | Jira only | AC6 | JQL `labels = parked` |
| T6 | `factory status`, `factory doctor .` recorded on CPID-44 | none | AC4 | output captured |
| T7 | Backend checks | none | AC7 | 262 passed, 3 skipped; ruff clean |
| T8 | PR, CI incl. CodeQL and sonarcloud, merge, Jira, Confluence change log | none | all | `gh pr checks` green |

## Data, API and migration impact

None. No application code, schema, API or dependency change.

## Security and failure modes

No secret is read or written; the main checkout's `.env` is not touched. The dismissal asks the owner to accept a
scanner exception: this item only proposes it. If the validator rejects a draft, the draft changes, not the validator.

## Rollout and rollback

Merge the PR. Rollback: revert the merge commit; no data or deploy involved. Jira labels are removed by hand if the
owner rejects the charter.

## Risks and open points

- The benchmark bar is a proposal; the owner may want another number.
- CPID-22 (no upload size limit) is a hardening item that the charter parks; the owner may prefer to make it a done
  criterion instead. Said in the charter record.
