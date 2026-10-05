# CPID-25 — Test plan: Remove employer branding

Status: draft · Risk: low · Jira: CPID-25

Test framework and conventions found: backend pytest (`uv run python -m pytest -q`, tests in `tests/`), ruff for lint and format; the frontend has no unit test suite, only `pnpm lint` and `pnpm build` (Next.js 16, eslint). This change is a pure rename with no new logic, so the proof is a repo-wide search plus build and lint plus a manual browser check. No test file is added: a unit test asserting that a string literal is absent would only restate the search.

| AC | Level | Test (name/path) | Happy | Boundary | Negative | Status |
|----|-------|------------------|-------|----------|----------|--------|
| AC1 | manual | `git grep -n -i -E "lt{2}s\|l[&]t\|lars[e]n"` from the repo root | no output, exit status 1 | case-insensitive; covers every tracked file including docs and lockfiles | before the change the same command lists 6 hits in 3 files (recorded in Jira) | planned |
| AC2 | manual | `git grep -n "chatpid_theme" frontend` and `git grep -n "_theme'" frontend` | 3 matches: layout.tsx (1), ThemeContext.tsx (2) | both files use the identical key string | no other `_theme` storage key remains | planned |
| AC3 | manual | `git diff` of the `@theme` block; `git grep -n "var(--color-" frontend` | only names changed, hex values identical | all 5 renamed entries checked, 9 untouched entries unchanged | no consumer of an old name exists | planned |
| AC4 | integration | `pnpm install --frozen-lockfile && pnpm lint && pnpm build` in `frontend/` | all exit 0 | n/a: the build covers the whole app | a missed import or syntax error would fail the build | planned |
| AC5 | manual | serve the built app, toggle the theme in a browser | toggle to dark, reload: opens dark; to light, reload: opens light | nothing saved: follows system preference | n/a: there is no invalid input path | planned |

## Regression risk

The backend is untouched; its 237 tests must stay green (run as a baseline guard). Frontend theme behaviour is covered only by the manual check since there is no frontend test suite.

## Untestable AC

None.

## Manual checks

AC5 needs a browser: `pnpm build && pnpm start` in `frontend/`, open the app, toggle the theme button, reload, and check the page class `dark` and the stored key `chatpid_theme` in DevTools. AC1 to AC3 are one-off command checks, marked manual because they are searches rather than repeatable test code. If no browser is available to the agent, AC5 is recorded as not run and reasoned from the diff (identical logic, only the key string changes).

## Audit (after implementation)

Results on the branch (2026-10-05):

- AC1: before the change the search listed 6 hits in 3 files (globals.css 3, layout.tsx 1, ThemeContext.tsx 2). After: no output, exit status 1, 0 hits. It would fail if any mention remained, since it is case-insensitive over all tracked files.
- AC2: `git grep -n "chatpid_theme" frontend` lists layout.tsx:12, ThemeContext.tsx:25 and ThemeContext.tsx:39; no other `_theme'` key exists.
- AC3: the diff of the `@theme` block changes five variable names and no hex value; no file in `frontend/` referenced any of the old names.
- AC4: `pnpm install --frozen-lockfile` ok; `pnpm build` exit 0 (compiled, TypeScript passed, 3 static pages). `pnpm lint` exits 1 with 3 errors and 6 warnings, all `react-hooks/set-state-in-effect` and similar rules in code this change did not touch beyond a string literal (ThemeContext.tsx:27 and others). Main has the identical result (3 errors, 6 warnings, checked on a clean checkout of main), so this is pre-existing lint debt, not introduced here; fixing them would be out of scope (behaviour must stay identical). Recorded for the owner.
- Backend guard: 237 passed, 3 skipped; `ruff check` and `ruff format --check` clean.
- AC5: not run in a browser (the agent has no browser). Reasoned from the diff: the only change to the theme code is the key string, applied identically in the inline script and the provider, so persistence and first paint behave as before. Manual check left for the owner.
