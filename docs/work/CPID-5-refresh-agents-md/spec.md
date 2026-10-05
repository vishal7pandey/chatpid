# CPID-5 — Refresh AGENTS.md: replace the stale Sprint-4 table with a pointer to the CPID board

Status: draft · Risk: low · Jira: CPID-5
Created: 2026-10-05 · Slug: refresh-agents-md

## Problem

`AGENTS.md` is the first file an agent or new engineer reads. Today about 170 lines of it are "Sprint 4/5
Status" tables whose rows point at `SCRUM-3xx` tickets that no longer exist, plus benchmark result tables that
cite result files removed in CPID-8. It also states facts that are no longer true (venv is Python 3.13.14,
default LLM provider is openai, a WSL/reboot note dated 2026-08-17), so readers get wrong setup guidance.

## Users and context

Coding agents and engineers onboarding to ChatP&ID. Files read: `AGENTS.md`, `pyproject.toml`,
`docker-compose.yml`, `.env.example`, `chatpid/config.py`, `scripts/*.py` (argparse flags), `.gitignore`
(which says benchmark results belong in Confluence/Jira, not git).

## Goals and non-goals

**Goals**
- AGENTS.md holds only durable, correct guidance plus a pointer to the CPID Jira board.
- The historic benchmark numbers are not lost: they move to a Confluence page.
- Every command left in the file runs (flags accepted).

**Non-goals**
- No change to the factory block between `<!-- factory:begin -->` and `<!-- factory:end -->`.
- No code, script or config changes; no re-running benchmarks.

## Requirements

- R1. AGENTS.md must contain no `SCRUM-` references and no `C:\Dev` paths, and the Sprint tables must be replaced by a pointer to the CPID board (https://vishal7pandey.atlassian.net/jira/software/projects/CPID/boards).
- R2. The retired status and benchmark-result content must be preserved in a Confluence page under the CPID space home, linked from AGENTS.md.
- R3. Durable notes (Python 3.12+/pydexpi, Neo4j via Docker Compose, LLM provider env var, key commands) must be kept and be accurate against the repo.
- R4. Every command in the remaining file must be runnable as written (script exists, flags exist).
- R5. The factory block must remain byte-identical.

## Acceptance criteria

- AC1. (R1) `grep -n "SCRUM-\|C:\\\\Dev" AGENTS.md` returns nothing; the file contains the CPID board URL.
- AC2. (R2) The Confluence page https://vishal7pandey.atlassian.net/wiki/spaces/CPID/pages/16711696 contains the tables and AGENTS.md links to it.
- AC3. (R3) Stated facts match the repo: requires-python from `pyproject.toml`, default provider and model from `chatpid/config.py` / `.env.example` / `docker-compose.yml`, Neo4j credentials point at `docker-compose.yml` rather than being duplicated.
- AC4. (R4) For each script named in AGENTS.md, `python scripts/<name>.py --help` exits 0 and lists every flag used in the documented command (`--level`, `--limit`, `--resume`, `--latest`, `--copies`, `--file`, `--levels`, `--document-id`). `ask.py` takes a positional question and has no argparse; verified by reading it.
- AC5. (R5) The text between the factory markers is identical to `main` (diff of the extracted block is empty), and `python .factory/verify.py` reports OK.

## Edge cases and failure modes

- A documented command that cannot run on a machine without Neo4j or an API key: documented as needing them; checked only for flags.
- `uv.lock` is git-ignored: `uv sync` regenerates it; the file says so rather than promising a lockfile.

## Non-functional requirements

- No secrets in the file (security.md); the dev Neo4j password stays only in `docker-compose.yml`.

## Assumptions

- The factory CODEOWNERS/verify rules treat AGENTS.md outside the block as freely editable.
- Archiving to Confluence (not a docs/ file) follows the `.gitignore` rule to record results in Confluence.

## Risks and dependencies

Low: documentation only, reversible by revert. Risk is a reader following a stale command; AC4 mitigates it.
