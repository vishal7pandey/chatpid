# CPID-43 — Plan: re-resolve the frontend transitive advisories in the lockfile

Status: plan-approved · Risk: low · Jira: CPID-43
Created: 2026-10-07 · Slug: frontend-transitive-advisories · Spec: spec.md

## Summary

Dependabot cannot update these packages, but every parent range already allows the patched versions, so `pnpm update ... --lockfile-only`
re-resolves them in `frontend/pnpm-lock.yaml`. One line of `frontend/package.json` moves (the `vitest` floor, written by pnpm). A guard
test written first fails on the current lockfile for each package.

**Size:** S

## Current state

`frontend/` uses pnpm 11.22.0 (`packageManager`), Next 16.3.6, vitest 4. `frontend/lib/lockfile-advisories.test.ts` already guards js-yaml
(CPID-36). The Python CI (`.github/workflows/ci.yml`) does not build or test the frontend (CPID-38), so the frontend commands run locally:
`CI=true pnpm install --frozen-lockfile`, `pnpm build`, `pnpm test`, `pnpm lint` (3 pre-existing errors). Backend: `uv run python -m pytest -q`
(262 passed, 3 skipped) and `uv run python -m ruff check .`.

## Approach

1. Add `frontend/lib/lockfile-transitive-advisories.test.ts` (same style as the js-yaml guard): for each package a table of the first
   patched version per major line; assert every package/snapshot entry and every dependent edge in `pnpm-lock.yaml` is at or above it.
2. `pnpm update source-map-js undici brace-expansion vitest @vitest/mocker --lockfile-only`.
3. pnpm leaves `brace-expansion@5.0.9` (under `minimatch@10.2.6`, range `^5.0.8`) in place. Resolve it with a temporary
   `overrides` entry in `pnpm-workspace.yaml`, `pnpm install --lockfile-only`, then restore the file (`git checkout`) and run
   `pnpm install --lockfile-only` again; the lock keeps 5.0.12 and no override remains.

**Alternatives rejected**
- A permanent `overrides` entry: not needed (parent ranges allow the fix) and it would outlive the parent's own bump.
- Bumping eslint or minimatch: a larger change than a lockfile re-resolution.
- `pnpm update --latest` or a full `pnpm update`: moves unrelated packages.
- Waiting for Dependabot: it fails with `security_update_not_possible` (10 failed runs in 7 days).

## Tasks

| # | Task | Files | Serves | Verify by |
|---|------|-------|--------|-----------|
| T1 | Failing guard test (red) | frontend/lib/lockfile-transitive-advisories.test.ts | AC1 | `pnpm test`: 10 failed on the current lockfile |
| T2 | Re-resolve the five packages (steps 2 and 3) | frontend/pnpm-lock.yaml, frontend/package.json | AC1 | `pnpm test`: 12 passed (new 10 + existing 2) |
| T3 | Frozen install, build, lint, backend | frontend, repo root | AC2 | `CI=true pnpm install --frozen-lockfile`, `pnpm build`, lint still 3 errors, pytest 262 passed 3 skipped, ruff clean |
| T4 | Work item docs, PR with the no-frontend-CI note | docs/work/CPID-43-... | AC1, AC2 | `python .factory/verify.py` OK; PR checks green |
| T5 | After merge: re-query alerts 4, 5, 12, 13, 14, 15, 16, 19, 20, 25, 26, 35 | none | AC3 | each `gh api .../dependabot/alerts/<id>` reads `fixed` |

## Data, API and migration impact

None (lockfile and a dev-dependency floor).

## Security and failure modes

Removes known vulnerable dev dependencies (path traversal in the vitest mocker, DoS in source-map-js and brace-expansion, cache poisoning in
undici). Fails closed: the guard test goes red if the lockfile regresses below any patched version. Supply-chain: pnpm's release-age and
integrity checks passed ("Lockfile passes supply-chain policies"); the newest new version (source-map-js 1.2.2) is 7 days old, the rest older.

## Rollout and rollback

Merge; Dependabot rescans the lockfile on the default branch; re-query each alert. Revert the commit to undo.

## Risks and open points

- The frontend job does not exist in CI (CPID-38): local install/build/test results are the evidence; stated in the PR.
- Dependabot may take time to mark alerts fixed; the tracking stays open until each reads `fixed`.
- If pnpm refuses an update because of a release-age setting the override route above is used, and the spec says so.
