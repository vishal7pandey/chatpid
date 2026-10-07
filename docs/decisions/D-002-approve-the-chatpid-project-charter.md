---
id: D-002
type: charter
title: Approve the ChatPID project charter
status: proposed
jira: CPID-44
proposed_by: Claude (agent)
proposed_at: '2026-10-07'
options:
- text: Approve the charter in docs/PROJECT.md as written
  recommended: true
decision: null
by: null
at: null
delegated: false
subject: docs/PROJECT.md
---
# Approve the ChatPID project charter

## Context

FACT-47 gives every project a written definition of done and a stop rule, so scope stops growing by default. ChatPID
has had none: eleven tickets are open with no order, and the work so far drifted between security fixes, benchmarks and
ideas. This record asks the owner to approve (or send back) the proposed `docs/PROJECT.md`: purpose, five done criteria,
non-goals, a parked list and the maintenance-mode rule. Approving stamps the file's hash; any later edit needs a new
charter decision. Ticket CPID-44, work item `docs/work/CPID-44-adopt-decision-gate-and-charter/`.

## Evidence

- Done criteria, each with one reference the factory checks offline (`factory status` shows them once approved):
  - C1 DEXPI files ingest into Neo4j end to end on the three reference drawings: `jira: CPID-45` (new, To Do). Today only
    unit tests with fakes cover `chatpid/ingest.py`; the live path is run by hand.
  - C2 the paper's 19-question benchmark reproduced and recorded: `metric` on `docs/eval/benchmark-latest.json`,
    key `correct_or_partial_fraction`, `min: 0.7`; ticket CPID-46 (new, To Do) produces the file. The bar is the agent's
    proposal from the Aug 2026 single-agent run on the conceptual graph (Confluence 16711696): 19 of 19 completed,
    6 correct, 8 partially correct, 5 incorrect, so 14 of 19 = 0.74 (the supervisor spike reached 17 of 19 = 0.89).
    The number is the owner's to change.
  - C3 licence of the DEXPI e.V. reference files in `data/dexpi_real/` resolved: `jira: CPID-27` (To Do, public repo
    tracks files its own notes say are not redistributed).
  - C4 CI runs the frontend build and tests: `jira: CPID-38` (To Do, no frontend job in `ci.yml` today).
  - C5 no open critical or high scanner finding: `jira: CPID-41`. It is the only open finding (the other ten `finding`
    tickets are Done) and it is waiting for the owner's answer to dismissal record D-001, so C5 depends on D-001.
- Non-goals: document scoping (CPID-11) and anything beyond the benchmark scope.
- Parked, each labelled `parked` in Jira with the comment "recommended by the agent, pending the owner's charter
  decision" (none closed or moved): CPID-10, 11, 17, 18, 19, 22, 26. CPID-21 ("sync the factory kit") is not listed
  because the CPID-44 work item does exactly that; the owner can close it after this merges.
- CPID-22 (no upload size limit, no auth on `POST /ingest`) is a hardening item rather than a scanner finding. It is
  parked here; if the owner wants it before calling the project done, make it a sixth criterion instead.
- `factory doctor` shows `no approved charter` until this is decided.

## Options

1. Approve the charter as written (recommended): the project gets an end (five criteria, all checkable) and a stop
   rule (maintenance mode: only security and dependency updates, anything else needs an amendment).
2. Send it back (`factory decide D-002 --reject --note "..."`): the agent revises `docs/PROJECT.md` and proposes again,
   for example with another benchmark bar, CPID-22 as a criterion, or a different parked list.

## Recommendation

Approve as written: every criterion has a ticket and a way to check it, the benchmark bar matches what the repo
measured, and the parked list keeps the remaining tickets visible without competing for attention.
