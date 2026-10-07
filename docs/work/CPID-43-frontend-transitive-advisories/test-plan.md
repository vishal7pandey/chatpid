# CPID-43 — Test plan: Frontend transitive advisories

Status: plan-approved · Risk: low · Jira: CPID-43

Test framework and conventions found: vitest 4 (`pnpm test` = `vitest run`) in `frontend/`, no config file, default node environment,
tests next to code as `*.test.ts` (`frontend/lib/lockfile-advisories.test.ts` is the model). Backend: `uv run python -m pytest -q`.

| AC | Level | Test (name/path) | Happy | Boundary | Negative | Status |
|----|-------|------------------|-------|----------|----------|--------|
| AC1 | unit | frontend/lib/lockfile-transitive-advisories.test.ts::<package> > resolves only patched versions in the package and snapshot entries (source-map-js, undici, brace-expansion, vitest, @vitest/mocker) | every `name@x.y.z` entry >= first patched for its major line | exactly the patched version passes (comparison is >=); brace-expansion checks the 1.x and 5.x lines separately | source-map-js@1.2.1, undici@8.10.0, brace-expansion@1.1.18 / 5.0.9, vitest and @vitest/mocker 4.1.10 each fail | verified |
| AC1 | unit | frontend/lib/lockfile-transitive-advisories.test.ts::<package> > has no dependent edge pinned to an unpatched version | every `name: x.y.z` edge >= first patched | n/a: same comparison | an edge to the old version fails (e.g. `source-map-js: 1.2.1` appears 4 times on main) | verified |
| AC2 | integration | `CI=true pnpm install --frozen-lockfile`, `pnpm build`, `pnpm test`, `pnpm lint`; backend pytest and ruff | install, build, tests succeed | n/a: command-level | lint error count not above the 3 pre-existing; pytest stays 262 passed, 3 skipped | verified |
| AC3 | manual | Dependabot alerts 4, 5, 12-16, 19, 20, 25, 26, 35 re-queried after merge | n/a: closure check | n/a | any state other than `fixed` keeps the ticket open | verified (2026-10-07, after merge of PR 33: all 12 alerts `fixed`; no open Dependabot alert left) |

## Regression risk

Only dev tooling resolves these packages (vitest runs the guard tests themselves, postcss/source-map-js, eslint/minimatch/brace-expansion,
jsdom/undici). The existing js-yaml guard and the lint result must not change; the Python suite is unaffected.

## Untestable AC

AC3 is a scanner state, checked by re-querying the alerts.

## Manual checks

After merge: `gh api repos/vishal7pandey/chatpid/dependabot/alerts/<id> --jq .state` for each id, expect `fixed`.

## Audit (after implementation)

Mutation audit (2026-10-07), the AC1 rows (frontend/lib/lockfile-transitive-advisories.test.ts, both `it` blocks inside `describe.each` over the five packages):

1. Lockfile of main (before the fix): all 10 tests fail, each naming its package: `source-map-js@1.2.1 is below 1.2.2` (entry and 4 edges),
   `undici@8.10.0 is below 8.10.2`, `brace-expansion@1.1.18 is below 1.1.21` and `brace-expansion@5.0.9 is below 5.0.12` (both lines flagged),
   `vitest@4.1.10 is below 4.1.11`, `@vitest/mocker@4.1.10 is below 4.1.11`. So every fixed package has a test that fails without the fix.
2. After the fix (`pnpm update ... --lockfile-only`, plus the temporary override for the brace-expansion 5.x line, no override left in the repo):
   `pnpm test` 2 files, 12 tests passed (10 new, 2 js-yaml).
3. Mutation: restoring only the brace-expansion 5.x line to 5.0.9 while keeping the 1.x line patched (the half-fixed state that
   `pnpm update` left first) fails only the brace-expansion tests: the per-major table is what catches it.

AC2: after the fix `CI=true pnpm install --frozen-lockfile` up to date (vitest 4.1.11), `pnpm build` compiled and generated pages, `pnpm lint`
9 problems = 3 errors (same as before) and 6 warnings, none in the new file; backend `uv run python -m pytest -q` 262 passed, 3 skipped;
`ruff check .` clean. AC3 is checked after merge by re-querying the alerts.
