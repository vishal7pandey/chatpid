# CPID-43 — Frontend transitive advisories: Dependabot cannot update them, the lockfile can

Status: spec-approved · Risk: low · Jira: CPID-43

## Repro

Environment: main @ 25ff543, `frontend/pnpm-lock.yaml`, pnpm 11.22.0, Node 24.

Open npm Dependabot alerts on `frontend/pnpm-lock.yaml` (`gh api --paginate "repos/vishal7pandey/chatpid/dependabot/alerts?state=open"`, all `state: open`):

| Package | Alerts | Severity | Vulnerable range | First patched | Locked before |
|---|---|---|---|---|---|
| source-map-js | 35 | high | >= 1.0.0, < 1.2.2 | 1.2.2 | 1.2.1 |
| undici | 12, 14 high; 13, 15, 19 low; 16, 20 medium | high | >= 8.10.0, < 8.10.2 | 8.10.2 | 8.10.0 |
| brace-expansion | 25 (5.x), 26 (1.x) | medium | >= 4.0.0, < 5.0.12 and < 1.1.21 | 5.0.12 / 1.1.21 | 5.0.9 and 1.1.18 |
| vitest | 5 | medium | >= 2.1.0, < 4.1.11 | 4.1.11 | 4.1.10 |
| @vitest/mocker | 4 | medium | >= 2.1.0, < 4.1.11 | 4.1.11 | 4.1.10 |

(vitest and @vitest/mocker were not in the ticket text; they are open npm alerts in the same lockfile with the same cause, so they are fixed here.)

Dependabot's own attempt fails: `Dependabot Updates` for `npm_and_yarn in /frontend` ends with `security_update_not_possible`
(runs 37497613594 source-map-js, 37488935762 undici; 10 failed runs in 7 days).

Automated repro (fails on the current lockfile):

- `cd frontend && pnpm test` runs `lib/lockfile-transitive-advisories.test.ts`; on main's lockfile all 10 tests fail, with
  `source-map-js@1.2.1 is below 1.2.2`, `undici@8.10.0 is below 8.10.2`, `brace-expansion@1.1.18 is below 1.1.21`,
  `brace-expansion@5.0.9 is below 5.0.12`, `vitest@4.1.10 is below 4.1.11`, `@vitest/mocker@4.1.10 is below 4.1.11`.

Reproducibility: always.

## Expected

The lockfile resolves each package at or above its first patched version, so each alert closes on Dependabot's next scan.

## Actual

The lockfile pins the older versions listed above, and Dependabot cannot move them.

## Root cause (with evidence)

- Where: `frontend/pnpm-lock.yaml` (resolved versions) and the Dependabot pnpm updater.
- Why it fails: all packages are transitive except vitest (a direct devDependency, range `^4.1.10`, lock at 4.1.10); every
  parent range already allows the patched version (e.g. `minimatch@10.2.6` declares `brace-expansion ^5.0.8`; `npm view` shows
  5.0.12), so the lockfile merely holds older in-range versions. Dependabot's pnpm helper exits before it reports a resolution,
  so the update is "not possible" with `conflicting-dependencies` empty. Same failure in sibling project ADE (ADE-64).
- Introduced by: always present; the patched releases (2026-09) came after the lock was resolved (2026-07/08).
- Evidence: `pnpm update source-map-js undici brace-expansion vitest @vitest/mocker --lockfile-only` resolves all but the
  5.x line of brace-expansion; pnpm 11.22.0 leaves `brace-expansion@5.0.9` under `minimatch@10.2.6` untouched even though
  5.0.12 satisfies `^5.0.8`. A temporary workspace override `brace-expansion@^5: ^5.0.12` followed by
  `pnpm install --lockfile-only` with the override removed again moves it to 5.0.12 and keeps it there (no override remains).

## Blast radius

- Dev and build tooling only: source-map-js (postcss), brace-expansion (minimatch via eslint), vitest and @vitest/mocker (test runner),
  undici (jsdom). Nothing here is a runtime dependency of the shipped Next.js app beyond what `next build` already bundles.
- `undici` moves 8.10.0 to 8.11.2 (a minor within its `^8` range); it is used by jsdom for tests.
- Alerts with a PR: none; none dismissed.

## Regression criterion (AC1)

AC1: `frontend/lib/lockfile-transitive-advisories.test.ts` passes after the fix and fails on the current lockfile, for each of
source-map-js, undici, brace-expansion (both the 1.x and 5.x lines), vitest and @vitest/mocker: no entry and no dependent edge
below the first patched version.

AC2: the frontend still installs, builds and tests as before: `CI=true pnpm install --frozen-lockfile`, `pnpm build`, `pnpm test`
succeed; `pnpm lint` shows the same 3 pre-existing errors; backend `uv run python -m pytest -q` stays 262 passed, 3 skipped, ruff clean.

AC3 (closure, not code): each of alerts 4, 5, 12, 13, 14, 15, 16, 19, 20, 25, 26 and 35 re-queried after the merge shows
`state: fixed`. Until then the tracking issue stays open; nothing is dismissed.

## Fix constraints

Lockfile re-resolution only. The one manifest change is the `vitest` floor in `frontend/package.json` (`^4.1.10` to `^4.1.11`),
which pnpm writes itself when it updates a direct dependency, and the lockfile importer specifier must match it for the frozen
install to pass. No override stays in the repository; no CI change (the frontend CI job is CPID-38); no other package moves beyond
what the re-resolution forces (the `@vitest/*` family follows vitest).

## Risks

Low: dev-tooling patch/minor bumps. The frontend has no CI job (CPID-38), so the PR's checks do not run the frontend; the
install, build and test results are recorded from local runs. Rollback: revert the commit.
