# CPID-36 — Test plan: js-yaml below 4.3.2 in the frontend lockfile

Status: plan-approved · Risk: medium · Jira: CPID-36

Test framework and conventions found: vitest 4 (`pnpm test` = `vitest run`) in `frontend/`, no config file, default node environment, tests next to code as `*.test.ts`; no frontend tests existed before this one.

| AC | Level | Test (name/path) | Happy | Boundary | Negative | Status |
|----|-------|------------------|-------|----------|----------|--------|
| AC1 | unit | frontend/lib/lockfile-advisories.test.ts::resolves js-yaml at or above the patched 4.3.2 everywhere | every `js-yaml@x.y.z:` entry >= 4.3.2 | exactly 4.3.2 passes (comparison is >=) | 4.3.1 in the lockfile fails | verified |
| AC1 | unit | frontend/lib/lockfile-advisories.test.ts::no dependent edge pins js-yaml to an unpatched version | every `js-yaml: x.y.z` edge >= 4.3.2 | n/a: same comparison | edge to 4.3.1 fails | verified |
| AC2 | integration | `CI=true pnpm install --frozen-lockfile`, `pnpm build`, `pnpm lint` | install and build succeed | n/a: command-level | lint error count not above the 3 pre-existing | verified |
| AC3 | manual | Dependabot alert 8 re-queried after merge | n/a: closure check | n/a | state must read `fixed`, else the ticket stays open | planned (after merge) |

## Regression risk

Only dev tooling resolves js-yaml (eslint). Lint results must not change; the Python suite is unaffected (not re-run beyond the baseline check).

## Untestable AC

AC3 is a scanner state; checked by re-querying the alert.

## Manual checks

After merge: `gh api repos/vishal7pandey/chatpid/dependabot/alerts/8`, expect `state: fixed`.

## Audit (after implementation)

Mutation audit (2026-10-05): (1) lockfile at js-yaml 4.3.1 (before the fix): both tests fail with `js-yaml@4.3.1 is below 4.3.2` and `edge to js-yaml 4.3.1 is below 4.3.2`. (2) After `pnpm update js-yaml` (4 lines changed in the lockfile, 4.3.1 -> 4.3.2): `pnpm test` 2 passed. Frozen install (`CI=true pnpm install --frozen-lockfile`) up to date, `pnpm build` compiled and generated pages, `pnpm lint` 9 problems = 3 errors (same as before) and 6 warnings, none in the new file; backend `uv run python -m pytest -q` 241 passed, 3 skipped. AC3 is checked after merge by re-querying alert 8.
