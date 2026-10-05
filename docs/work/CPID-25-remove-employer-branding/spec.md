# CPID-25 — Remove employer branding

Status: draft · Risk: low · Jira: CPID-25
Created: 2026-10-05 · Slug: remove-employer-branding

Note on wording: this document deliberately never spells the former employer's name or its abbreviations, so
that the repo-wide search in AC1 can return zero hits. The search pattern is written as a regex that does not match itself.

## Problem

ChatPID is a personal project, but its frontend carries the branding of the owner's former employer: a CSS
palette named after that employer's brand, comments that say the tokens were ported from that brand palette, and a
`localStorage` key for the theme that embeds the employer's abbreviation. The owner directed (2026-10-05) that every
mention of the former employer be removed from the repo's current files.

## Users and context

The owner and any reader of the public repo. The affected code is the Next.js frontend:
`frontend/app/globals.css` (design tokens), `frontend/app/layout.tsx` (inline script that applies the saved theme
before first paint) and `frontend/context/ThemeContext.tsx` (theme provider and toggle). Found with
`git grep -n -i -E "lt{2}s|l[&]t|lars[e]n"`: 6 hits in 3 files, all in the frontend.

## Goals and non-goals

**Goals**
- No mention of the former employer (name, abbreviation, brand palette names) in any current tracked file.
- No visual change and no behaviour change in the theme toggle.

**Non-goals**
- Rewriting git history. The term also appears in the history of the public repo (the frontend scaffold commit of
  2026-08-17). A rewrite is destructive for a public repo; it is a separate step the owner decides and the lead performs.
- Redesigning the palette or the token system. Colour values stay as they are.
- Editing the Jira ticket text, which quotes the term to describe the problem.

## Requirements

- R1. The theme `localStorage` key must be a neutral name (`chatpid_theme`) in `layout.tsx` and `ThemeContext.tsx`, and both must use the same key.
- R2. The CSS `@theme` palette entries that carry the employer's brand names must be renamed to neutral names with unchanged colour values. Nothing references the old names, so no consumer changes.
- R3. Comments in `globals.css` must describe the token system without naming the former employer.
- R4. Theme behaviour must be unchanged: toggle switches light/dark, persists across reloads, and the first paint honours the saved choice or the system preference.
- R5. The frontend must still lint and build.

## Acceptance criteria

- AC1. (R1, R2, R3) `git grep -n -i -E "lt{2}s|l[&]t|lars[e]n"` on the branch returns no output (exit status 1). Git history is excluded.
- AC2. (R1, R4) The key read by the inline script in `layout.tsx` and the key read and written in `ThemeContext.tsx` are both `chatpid_theme`: `git grep -n "chatpid_theme" frontend` shows exactly three matches (one in layout.tsx, two in ThemeContext.tsx) and no other `_theme` storage key remains.
- AC3. (R2) Every colour value in the `@theme` block of `globals.css` is identical before and after (the diff of the block shows only variable names changed), and no file in `frontend/` references a renamed variable.
- AC4. (R5) `pnpm install --frozen-lockfile`, `pnpm lint` and `pnpm build` in `frontend/` succeed. Failure path: if build or lint fails, the change is not merged.
- AC5. (R4) In a browser (manual): load the app, toggle to dark, reload; the app opens dark with no flash. Toggle to light, reload; it opens light. With nothing saved, it follows the system preference.

## Edge cases and failure modes

- A browser that has the old key saved: the old key is no longer read, so that browser falls back to the system preference once, and the next toggle stores `chatpid_theme`. The stale old entry stays in that browser's storage, harmless and unread. See Assumption A1.
- `localStorage` unavailable (private mode): unchanged; the inline script is wrapped in try/catch and the provider behaviour is unchanged.

## Non-functional requirements

- Security/privacy: nothing touched; no secrets involved.
- Compatibility: pure rename; no API or data contract involved. Backend untouched (237 tests must still pass).

## Assumptions

- A1. The ticket suggests a one-time read of the old key so an existing saved theme survives. That is not possible while AC1 holds, because reading the old key requires the old key string in the source (building the string in pieces to dodge the search would defeat the purpose of the removal). The owner's directive that no mention remain takes precedence. Cost: a browser with a saved theme falls back to the system preference once. This is a personal single-user project, so the cost is negligible. Overrule here if a migration is wanted.
- A2. The other palette names in the same `@theme` block that are that brand's colour names (four more) are also renamed, as the directive covers any brand palette derived from the employer's. Values are unchanged.
- A3. History rewriting is out of scope and happens as a separate owner-approved step.

## Risks and dependencies

Low: renames in three files plus a docs-only work item, no consumers of the renamed CSS variables, easily reverted. The Jira ticket asks to wait for the CPID-14 frontend wave; no pull request is open (verified with `gh pr list`), so there is no conflict.
