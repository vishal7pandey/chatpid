# CPID-36 — js-yaml below 4.3.2 in the frontend lockfile: Dependabot alert 8

Status: spec-approved · Risk: medium · Jira: CPID-36

## Repro

Environment: main @ 20e910e, `frontend/pnpm-lock.yaml`, pnpm 11.22.0, Node 24.

Dependabot alert 8 (`gh api repos/vishal7pandey/chatpid/dependabot/alerts/8`): package `js-yaml` (npm), manifest
`frontend/pnpm-lock.yaml`, severity high, "maxTotalMergeKeys does not limit CPU use for empty merge sources",
vulnerable range `>= 4.0.0, < 4.3.2`, first patched version `4.3.2`, state `open`. The lockfile resolves `js-yaml@4.3.1`.

Automated repro (fails on the current lockfile, passes after the fix):

- `cd frontend && CI=true pnpm install --frozen-lockfile && pnpm test` runs `lib/lockfile-advisories.test.ts`;
  before the fix 2 tests fail: `js-yaml@4.3.1 is below 4.3.2` and `edge to js-yaml 4.3.1 is below 4.3.2`.

Reproducibility: always.

## Expected

The lockfile resolves `js-yaml` at `4.3.2` or later, so the alert closes on Dependabot's next scan.

## Actual

`js-yaml@4.3.1` is locked (lockfile lines for the package entry and the edge from `@eslint/eslintrc@3.3.6`).

## Root cause (with evidence)

- Where: `frontend/pnpm-lock.yaml`, `js-yaml@4.3.1`. It is transitive only: `pnpm why js-yaml` shows eslint 9 ->
  `@eslint/eslintrc@3.3.6` -> `js-yaml`. `@eslint/eslintrc@3.3.6` declares `js-yaml: ^4.3.0`, which already allows 4.3.2.
- Why it fails: the lockfile pins an older in-range version; 4.3.2 was published after the lock was last resolved.
- Introduced by: always present in the lockfile since it was resolved at 4.3.1; Dependabot's next bump (0bd2c29) did not touch it.
- Evidence: the 2 failing tests above; `npm view @eslint/eslintrc@3.3.6 dependencies.js-yaml` returns `^4.3.0`.

## Blast radius

- Dev tooling only (eslint config loading); `js-yaml` is not a dependency of the shipped app or of `next build` output.
- No other package in the lockfile resolves `js-yaml` (single version). No override or parent bump is needed because the parent's range already admits the fix.

## Regression criterion (AC1)

AC1: `frontend/lib/lockfile-advisories.test.ts` passes after the fix and fails on the current lockfile: no `js-yaml`
version in `pnpm-lock.yaml` below 4.3.2.

AC2: the frontend still installs, builds and lints as before: `CI=true pnpm install --frozen-lockfile`, `pnpm build`
succeed; `pnpm lint` shows the same 3 pre-existing errors, no more.

AC3 (closure, not code): Dependabot alert 8 re-queried after the merge shows `state: fixed`. Until then CPID-36 stays open.

## Fix constraints

Lockfile-only change (re-resolve `js-yaml` within its existing range); no `package.json` change, no override, no other
package bumped beyond what the re-resolution forces. Do not touch other alerts.

## Risks

Medium: a transitive dev-tool bump; eslint could behave differently if the parse of a YAML config changed (none used here).
Rollback: revert the commit.
