# CPID-44 — Adopt decision gate and charter

Status: draft · Risk: low · Jira: CPID-44
Created: 2026-10-07 · Slug: adopt-decision-gate-and-charter

## Problem

The factory now has an owner-decisions gate (FACT-46: records in `docs/decisions/`, answered only by the owner with
`factory decide`) and a project charter (FACT-47: `docs/PROJECT.md`, the written definition of done and the stop rule).
ChatPID has neither. Its open questions to the owner live in Jira comments (the proposed dismissal on CPID-41) and in
chat, where they are easy to lose, and nothing says when the project is finished, so scope grows by default (CPID-11,
17, 18, 19, 22, 26 are all open with no priority order).

## Users and context

The repo owner (decides) and the agents working in this repo (propose). Touches factory-managed files (from
`factory sync`), two new files under `docs/decisions/`, the charter `docs/PROJECT.md`, and this work item. No
application code. Grounded in `factory sync --dry-run .`, the validators in `swfactory/decisions.py` and
`swfactory/charter.py`, the CPID ticket history and the Aug 2026 benchmark page (Confluence 16711696).

## Goals and non-goals

**Goals**
- Bring the kit to the factory's current version (the decision template, the charter template, updated skills,
  policies and `verify.py`).
- Turn the open dismissal question of CPID-41 into a `dismissal` decision record, status `proposed`.
- Draft the charter `docs/PROJECT.md` with measurable done criteria and a `charter` decision record, status `proposed`.
- Make both records show as waiting for the owner in `factory status` and `factory doctor`.
- Label the open CPID tickets that the done criteria do not need as `parked`, and open the missing tickets that the
  criteria point at.

**Non-goals**
- Accepting or rejecting either record: only the owner runs `factory decide`; this item never does.
- Dismissing the Sonar alert, or any change to `chatpid/api.py`.
- Doing the work behind the done criteria (CPID-45, CPID-46, CPID-27, CPID-38 stay open).
- Closing or moving any parked ticket.
- `--force` sync.

## Requirements

- R1. `factory sync .` runs without `--force`; a locally modified managed file is not overwritten.
- R2. A `dismissal` record for SonarCloud issue `AaESVCox-B_YsUej5pDi` (rule `pythonsecurity:S2083`,
  `chatpid/api.py:362`, project `vishal7pandey_chatpid`) exists, `proposed`, reason `false positive`, linked to CPID-41,
  with the evidence and the two options.
- R3. `docs/PROJECT.md` is a valid charter: purpose in two sentences, mode `active`, 3 to 7 done criteria each with
  exactly one offline-checkable reference, non-goals, parked list, a `## Maintenance mode` section; its `decision`
  names a `charter` record whose status is `proposed`.
- R4. The benchmark bar in the charter is grounded in what the repo measures today and is stated as the owner's to
  change.
- R5. Open tickets not needed by the criteria carry the `parked` label and a comment; none is closed or moved.
- R6. The state is checked and recorded: `sync --check`, `verify.py`, `factory status`, `factory doctor`, backend tests.

## Acceptance criteria

- AC1. After `factory sync .`, `factory sync --check .` exits 0 and `python .factory/verify.py` passes; a deliberate
  local edit to a managed file makes `sync --check` exit non-zero and restoring it makes it exit 0. (R1, R6)
- AC2. `docs/decisions/D-001-*.md` is a `dismissal` with `alert`, `reason: false positive`, `jira: CPID-41`, two options
  with exactly one recommended, status `proposed`, no placeholder text; `verify.py` accepts it. (R2)
- AC3. `docs/PROJECT.md` passes the charter validator and the charter state is "unapproved: decision D-002 is waiting
  for the owner", not `invalid` or `template`; the record `D-002` is `charter`, `subject: docs/PROJECT.md`, `proposed`. (R3)
- AC4. `factory status` lists both records under "waiting for the owner" and `factory doctor .` reports them; the
  doctor output is recorded on CPID-44. (R6)
- AC5. Every done criterion has exactly one reference, and each Jira key it names exists. The benchmark criterion
  names its bar, its source numbers and says the number is the owner's to change. (R3, R4)
- AC6. The tickets in the parked list are labelled `parked` with the comment "recommended by the agent, pending the
  owner's charter decision"; none changed status. (R5)
- AC7. Backend baseline is unchanged: 262 passed, 3 skipped, `ruff check` clean. (R6)
- AC8. No record or charter has status `accepted`, no `decision`, `by` or `at` is set, and `factory decide` was never
  run by this item. (non-goal)

## Edge cases and failure modes

- A locally modified managed file: sync skips it; stop and report on CPID-44.
- The charter validator rejects the draft (for example a vague word or a bad reference): fix the draft, never the
  validator.
- An earlier Sonar key (`AaESHd3k4FTZ_gsvTVdz`) was already closed; the record names only the current open one and
  mentions the earlier one as history.
- A referenced criterion (metric file) does not exist yet: that is "not met", not an error; the criterion is
  deliberately not met until CPID-46 lands.

## Non-functional requirements

- Security (`.factory/policies/security.md`): the main checkout's `.env` is not opened, read or printed; no secret is
  written. The dismissal text contains no secret.
- Reversible: one revert of the merge commit removes the records, the charter and the sync.

## Assumptions

- The owner has delegated spec and plan approval and merging for this item (recorded as delegated).
- The benchmark bar `correct_or_partial_fraction >= 0.7` is a proposal derived from the Aug 2026 single-agent run
  (14 of 19 = 0.74); the owner may change it in the charter decision.
- CPID-41 stays open until the owner answers D-001, so criterion C5 is not met yet.

## Risks and dependencies

- Low risk: process and documentation files only.
- Dependency on the owner for D-001 and D-002; until they answer, the charter is unapproved and the alert stays open.

## Open questions

None for this item; the questions it raises are the two decision records.
