# CPID-5 — Plan: Refresh AGENTS.md

Status: draft · Risk: low · Jira: CPID-5
Created: 2026-10-05 · Slug: refresh-agents-md · Spec: spec.md

## Summary

Archive the Sprint 4/5 tables and benchmark result sections to a Confluence page, rewrite the non-factory part
of `AGENTS.md` into short, verified setup notes plus a board pointer, and prove it with greps and `--help` runs.

**Size:** S

## Current state

`AGENTS.md` lines 1-211 are project notes (sprint tables from line 45 to 192), lines 213-250 are the managed
factory block. Run commands: `.venv/Scripts/python.exe -m pytest`, scripts under `scripts/`.

## Approach

Edit only the text above `<!-- factory:begin -->`. Confluence page already created (id 16711696) with the
archived content. Replace "Neo4j Setup" Docker/WSL history with the actual steps from `docker-compose.yml`.

**Alternatives rejected**
- Keep the tables in AGENTS.md as history: they cite deleted tickets and files; the ticket asks to remove them.
- Archive into `docs/*.md`: `.gitignore` says results are recorded in Confluence/Jira, not git.

## Tasks

| # | Task | Files | Serves | Verify by |
|---|------|-------|--------|-----------|
| T1 | Archive old content to Confluence (done before branch) | Confluence 16711696 | AC2 | page readable |
| T2 | Rewrite AGENTS.md above the factory block | AGENTS.md | AC1, AC3, AC5 | grep, block diff |
| T3 | Run every documented script with `--help` | scripts/*.py | AC4 | exit 0, flags listed |
| T4 | Work item docs, verify.py | docs/work/CPID-5-refresh-agents-md | AC5 | `python .factory/verify.py` |

## Data, API and migration impact

None.

## Security and failure modes

No secrets added; the dev password is referenced by file name only.

## Rollout and rollback

Merge; revert the commit to undo. The Confluence page can stay.

## Risks and open points

- A flag documented but renamed: caught by T3.
