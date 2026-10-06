# CPID-39 — Sync the factory kit

Status: draft · Risk: low · Jira: CPID-39
Created: 2026-10-06 · Slug: sync-the-factory-kit · Spec: spec.md

## Summary

Run the factory CLI's `sync` on a feature branch, then fix the two things sync does not own: stale work
item state and action versions in the user-owned `ci.yml`. Verify with the factory's own checks and the
project's backend checks, then merge through a PR once CI (including the new dormant `sonar` job) is green.

**Size:** S

## Current state

- `factory sync --dry-run .` plans 5 creates (Sonar workflow and properties, `findings.md`, the
  `factory-findings` skill in `.claude/skills` and `.github/skills`) and 14 updates (AGENTS.md block,
  `factory-verify.yml`, `.factory/verify.py`, `factory.yaml`, policies `autonomy.md` and `security.md`,
  skills `factory-implement`, `factory-release`, `factory-test`, `factory-workflow` in both skill dirs).
  Skipped as user-owned: `CLAUDE.md`, `copilot-instructions.md`, PR template, `CODEOWNERS`, `ci.yml`,
  `docs/work/README.md`.
- `.github/workflows/ci.yml` uses `checkout@v4`, `setup-python@v5`, `setup-uv@v5`; the kit template
  (`kit/ci/python.yml`) uses `@v7`, `@v7`, `@v10.2.0`.
- Eight items are `in-review` with merged PRs: CPID-12 (#14), 14 (#13), 15 (#15), 20 (#10), 23 (#11),
  25 (#16), 34 (#20), 36 (#21).
- Checks: `uv run python -m pytest -q`, `uv run ruff check .`, `python .factory/verify.py`.

## Approach

Use the CLI as designed: `sync` without `--force`, then `sync --check`. Touch nothing else by hand
except the minimum named above. This is the smallest change that satisfies the spec.

**Alternatives rejected**
- `sync --force` — would overwrite local edits to managed files; forbidden by AC2.
- Copying the kit's whole CI template over `ci.yml` — would drop the project's own `uv lock --check` and
  `--frozen` steps; only version bumps are wanted.

## Tasks

| # | Task | Files | Serves | Verify by |
|---|------|-------|--------|-----------|
| T1 | Review `sync --dry-run .` output | none | AC1 | output matches the list above |
| T2 | `factory sync .` (no `--force`) | managed files, new Sonar files | AC1, AC2, AC3 | no conflict reported; `sync --check .` exit 0 |
| T3 | Mark merged items `merged` with `pr` string | 8 `docs/work/*/item.yaml` | AC5 | `gh pr view <n> --json state` is MERGED; `python .factory/verify.py` passes |
| T4 | Bump action versions in `ci.yml` | `.github/workflows/ci.yml` | AC6 | `git diff` shows only 3 `uses:` lines; CI green |
| T5 | Deliberate break: edit a managed file, run `sync --check`, restore | one managed file (temporary) | AC2 | check exits non-zero, then 0 after restore |
| T6 | Run `factory doctor .`, record harden and sonar lines | none | AC4 | output captured in notes and on the ticket |
| T7 | Backend checks | none | AC7 | 241 passed, 3 skipped; ruff clean |
| T8 | PR, wait for CI incl. `sonar` job, merge, update Jira and Confluence change log | none | AC3, AC6 | `gh pr checks` all green |

## Data, API and migration impact

None. No application code, schema, API or dependency change. `ci.yml` gains newer action versions only.

## Security and failure modes

No secrets touched; `.env` is not opened. The Sonar workflow's guard skips with a notice until the owner
sets the org key and `SONAR_TOKEN`; if the guard were wrong the `sonar` job would fail on the PR and the
merge would wait. A nonexistent action tag would fail CI on the PR, visibly.

## Rollout and rollback

Merge the PR. Rollback: revert the merge commit (`git revert -m 1 <sha>`); no data or deploy is involved.
No point of no return.

## Risks and open points

- The stricter `verify.py` may flag an existing item: fix the item metadata, do not weaken the gate.
- The new `sonar` job might not pass dormant: check the first CI run before merging.
