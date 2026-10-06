# CPID-36 — Plan: re-resolve js-yaml to 4.3.2 in the frontend lockfile

Status: plan-approved · Risk: medium · Jira: CPID-36
Created: 2026-10-05 · Slug: js-yaml-below-4-3-2-in-frontend · Spec: spec.md

## Summary

`js-yaml` is only transitive (eslint -> `@eslint/eslintrc@3.3.6`, range `^4.3.0`), so the smallest correct fix is to
re-resolve it in `frontend/pnpm-lock.yaml` to 4.3.2 (`pnpm update js-yaml`), with no override and no parent bump.
A vitest guard test written first fails on the current lockfile.

**Size:** S

## Current state

`frontend/` uses pnpm 11.22.0 (`packageManager`), Next 16.3.6, eslint 9. `vitest` is a devDependency with no tests yet.
`pnpm lint` has 3 pre-existing errors. The Python CI (`.github/workflows/ci.yml`) does not build the frontend; the
frontend commands are run locally: `CI=true pnpm install --frozen-lockfile`, `pnpm build`, `pnpm test`, `pnpm lint`.

## Approach

Add `frontend/lib/lockfile-advisories.test.ts` (reads `pnpm-lock.yaml`, asserts every `js-yaml` entry and edge is >= 4.3.2).
Run `pnpm update js-yaml` in `frontend/`; if pnpm does not move transitive deps, edit nothing by hand: use
`pnpm update --latest` limited to the name, or an override as a last resort.

**Alternatives rejected**
- `pnpm.overrides` for js-yaml: not needed, the parent's range already allows 4.3.2; an override would live on after the parent moves on.
- Bumping eslint or `@eslint/eslintrc`: larger change than a lockfile re-resolution.

## Tasks

| # | Task | Files | Serves | Verify by |
|---|------|-------|--------|-----------|
| T1 | Failing guard test (red) | frontend/lib/lockfile-advisories.test.ts | AC1 | 2 failed on current lockfile |
| T2 | Re-resolve js-yaml to >= 4.3.2 | frontend/pnpm-lock.yaml | AC1 | `pnpm test` 2 passed |
| T3 | Frozen install, build, lint | frontend | AC2 | `CI=true pnpm install --frozen-lockfile`, `pnpm build` ok, lint still 3 errors |
| T4 | After merge: re-query Dependabot alert 8 | none | AC3 | `gh api .../dependabot/alerts/8` state `fixed` |

## Data, API and migration impact

None (lockfile only).

## Security and failure modes

Removes a known vulnerable dev dependency. Fails closed: the guard test goes red if the lockfile regresses below 4.3.2.

## Rollout and rollback

Merge; Dependabot rescans the lockfile on the default branch; re-query. Revert the commit to undo.

## Risks and open points

- pnpm may refuse 4.3.2 because of a release-age setting; then use an override and say so in the spec.
- Dependabot might need minutes to hours to mark the alert fixed; the ticket stays open until it does.
