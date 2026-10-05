# CPID-25 — Remove employer branding

Status: draft · Risk: low · Jira: CPID-25
Created: 2026-10-05 · Slug: remove-employer-branding · Spec: spec.md

## Summary

Rename the theme `localStorage` key to `chatpid_theme` in the two files that use it, rename the employer-branded
palette variables in the `@theme` block of `globals.css` to neutral `--color-brand-*` names keeping the values, and
reword the two comments. No behaviour or visual change.

**Size:** S

## Current state

- `frontend/app/globals.css`: the header comment says the tokens were ported from another project's brand palette; a token-naming comment calls `--brand-*` the colors of that palette; the `@theme` block defines `--color-<name>` entries (5 carry that employer's palette names, the rest are generic colours). Nothing else in `frontend/` references any `--color-*` variable (only `--brand-primary`, `--brand-accent`, `--brand-navy` in `:root`, which are generic names and stay).
- `frontend/app/layout.tsx`: inline script `themeInitScript` reads the theme key before first paint.
- `frontend/context/ThemeContext.tsx`: reads the key in an effect, writes it in `toggleTheme`.
- Commands: backend `uv run python -m pytest -q`, `uv run ruff check .`, `uv run ruff format --check .`; frontend (in `frontend/`) `pnpm install --frozen-lockfile`, `pnpm lint`, `pnpm build`. CI (`ci.yml`) only runs the backend; the frontend is verified locally. There is no frontend unit test suite in the repo.

## Approach

Plain rename. A shared constant for the key would be cleaner, but the inline script in `layout.tsx` is a string that
runs before React, so it cannot import it; two literals kept in sync (checked by AC2) is the smallest change.

Palette renames (values unchanged): the navy entry becomes `--color-brand-navy`, mobility blue becomes
`--color-brand-blue`, the brand green becomes `--color-brand-green`, the brand yellow becomes `--color-brand-yellow`,
electric blue becomes `--color-brand-cyan`. The other entries are generic colour names and stay.

**Alternatives rejected**
- Keep a one-time migration read of the old key: needs the old string in source, contradicts AC1 (spec A1).
- Obfuscate the old key (concatenation) to migrate: defeats the intent of the removal.
- Leave the generic-looking names (green, yellow, two blues): they are the employer's brand colour names; the directive covers them.

## Tasks

| # | Task | Files | Serves | Verify by |
|---|------|-------|--------|-----------|
| T1 | Rename the theme storage key to `chatpid_theme` | `frontend/app/layout.tsx`, `frontend/context/ThemeContext.tsx` | AC1, AC2, AC5 | `git grep -n "chatpid_theme" frontend` shows 3 matches |
| T2 | Rename the five brand palette variables, reword the two comments | `frontend/app/globals.css` | AC1, AC3 | diff shows only names and comments changed; no reference to old names |
| T3 | Run lint, build and the backend suite; self-check AC1 | n/a | AC1, AC4 | `pnpm lint`, `pnpm build` exit 0; the search from the spec exits 1; backend 237 passed |
| T4 | Manual theme persistence check | n/a | AC5 | built app served locally; toggle and reload observed, or recorded as not run if no browser is available |

## Data, API and migration impact

None. One browser storage key renamed (spec A1: the old value is not migrated). No backend, API, schema or config change.

## Security and failure modes

No auth, secrets or PII. Failure mode: a missed reference to an old CSS variable would render without that colour; mitigated by the repo-wide search (nothing referenced them) and by the build.

## Rollout and rollback

Merge to main; the frontend has no deploy environment configured (`environments` are null). Rollback: revert the merge commit.

## Risks and open points

- A stale reference in a file outside `frontend/` (docs, README): the repo-wide search in AC1 covers every tracked file.
- Git history still contains the term; handled outside this item.
